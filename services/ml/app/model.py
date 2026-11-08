"""Per-user model (ARCHITECTURE.md 8.4): one StandardScaler + IsolationForest per modality, percentile-calibrated.

Each modality (keys, mouse, touch) is fit only on the enrollment windows where that modality is present, so a
browsing window with no typing is never compared against imputed typing features. Mouse uses shape and click
features only: speed, acceleration and scroll depend on the task (click-target game vs. browsing) more than on
the person, and on the Stage 5 data they flagged the owner's own browsing.

Files under MODELS_DIR/{userId}/: model.joblib, meta.json, training.parquet (the windows the current model was fit
on), features.parquet (every window, for debugging/plots).
"""

import json
import math
import os
import re
import time
from pathlib import Path
from threading import Lock

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .features import KEY_FEATURES, TOUCH_FEATURES

MODELS_DIR = Path(os.environ.get("MODELS_DIR", Path(__file__).resolve().parent.parent / "models"))
MIN_WINDOWS = 20  # total enrollment windows
MIN_MODALITY_WINDOWS = 8  # a modality with fewer enrollment windows is not scored for this user
MAX_TRAINING_WINDOWS = 300  # feedback retraining keeps the most recent windows
FORMAT = 2

MOUSE_MODEL_FEATURES = [
    "straightness", "angle_mean", "angle_std", "pause_mean", "click_hold_mean", "click_hold_std",
]
MODALITIES: dict[str, tuple[list[str], str]] = {
    "keys": (KEY_FEATURES, "has_keys"),
    "mouse": (MOUSE_MODEL_FEATURES, "has_mouse"),
    "touch": (TOUCH_FEATURES, "has_touch"),
}

# Calibration: a window's IF score is placed in the user's training-score distribution. Windows above the
# CALIB_QUANTILE of training scores look like the user (risk 0); below it, risk rises linearly to 1 at the
# least-typical training window and beyond. Plain `1 - percentile` makes genuine windows uniform on 0..1,
# which sits above the critical step-up threshold on average.
CALIB_QUANTILE = 0.25

_lock = Lock()
_cache: dict[str, tuple[int, dict]] = {}  # userId -> (version, bundle)


def user_dir(user_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", user_id):  # ids become paths; Better Auth ids are alnum
        raise ValueError("bad user id")
    return MODELS_DIR / user_id


def meta(user_id: str) -> dict | None:
    path = user_dir(user_id) / "meta.json"
    return json.loads(path.read_text()) if path.exists() else None


def _matrix(rows: list[dict[str, float]], cols: list[str]) -> np.ndarray:
    return np.array([[r.get(c, math.nan) for c in cols] for r in rows], dtype=float).reshape(len(rows), len(cols))


def _fit(X: np.ndarray) -> dict:
    medians = np.nanmedian(np.where(np.isnan(X).all(axis=0), 0.0, X), axis=0)  # all-NaN column -> 0
    X = np.where(np.isnan(X), medians, X)
    scaler = StandardScaler().fit(X)
    forest = IsolationForest(n_estimators=200, contamination="auto", random_state=42).fit(scaler.transform(X))
    train_scores = np.sort(forest.decision_function(scaler.transform(X)))
    return {"scaler": scaler, "forest": forest, "medians": medians, "train_scores": train_scores}


def train(user_id: str, rows: list[dict[str, float]]) -> dict:
    """Fit every modality with enough windows and persist. Returns meta.json contents.
    Raises ValueError if no modality has enough windows."""
    mods = {}
    for name, (cols, flag) in MODALITIES.items():
        present = [r for r in rows if r.get(flag) == 1.0]
        if len(present) >= MIN_MODALITY_WINDOWS:
            mods[name] = {**_fit(_matrix(present, cols)), "features": cols, "windows": len(present)}
    if not mods:
        raise ValueError(f"no modality has {MIN_MODALITY_WINDOWS}+ windows; type and use the mouse during enrollment")

    prev = meta(user_id)
    info = {
        "version": (prev["version"] + 1) if prev else 1,
        "format": FORMAT,
        "windowCount": len(rows),
        "modalities": {n: m["windows"] for n, m in mods.items()},
        "trainedAt": time.time(),
    }
    d = user_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    bundle = {"format": FORMAT, "modalities": mods}
    pd.DataFrame(rows).to_parquet(d / "training.parquet", index=False)
    joblib.dump(bundle, d / "model.joblib")
    (d / "meta.json").write_text(json.dumps(info, indent=2))
    with _lock:
        _cache[user_id] = (info["version"], bundle)
    return info


def training_rows(user_id: str) -> list[dict[str, float]]:
    path = user_dir(user_id) / "training.parquet"
    return pd.read_parquet(path).to_dict("records") if path.exists() else []


def retrain_with(user_id: str, new_rows: list[dict[str, float]]) -> dict | None:
    """Append verified-genuine windows to the training set and refit (feedback after step-up, principle 5)."""
    base = training_rows(user_id)
    if not base:
        return None  # never enrolled: feedback must not create a template
    return train(user_id, (base + new_rows)[-MAX_TRAINING_WINDOWS:])


def _load(user_id: str) -> dict | None:
    info = meta(user_id)
    if info is None or info.get("format") != FORMAT:
        return None  # not enrolled, or a Stage 5 model: run scripts/retrain.py
    with _lock:
        hit = _cache.get(user_id)
        if hit and hit[0] == info["version"]:
            return hit[1]
    bundle = joblib.load(user_dir(user_id) / "model.joblib")
    with _lock:
        _cache[user_id] = (info["version"], bundle)
    return bundle


def calibrate(train_scores: np.ndarray, score: float) -> float:
    pct = np.searchsorted(train_scores, score, side="right") / len(train_scores)
    return float(np.clip((CALIB_QUANTILE - pct) / CALIB_QUANTILE, 0.0, 1.0))


def window_risk(user_id: str, feats: dict[str, float]) -> dict[str, float] | None:
    """Risk in [0, 1] per modality present in this window and modeled for this user ({} if none).
    None if the user has no usable model."""
    b = _load(user_id)
    if b is None:
        return None
    out = {}
    for name, m in b["modalities"].items():
        if feats.get(MODALITIES[name][1]) != 1.0:
            continue
        x = _matrix([feats], m["features"])
        x = np.where(np.isnan(x), m["medians"], x)
        score = m["forest"].decision_function(m["scaler"].transform(x))[0]
        out[name] = calibrate(m["train_scores"], score)
    return out
