"""Per-user model (ARCHITECTURE.md 8.4): StandardScaler + IsolationForest with percentile calibration.

Files under MODELS_DIR/{userId}/: model.joblib, meta.json, features.parquet (every window, for debugging/plots).
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
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .features import FEATURES

MODELS_DIR = Path(os.environ.get("MODELS_DIR", Path(__file__).resolve().parent.parent / "models"))
MIN_WINDOWS = 20

_lock = Lock()
_cache: dict[str, tuple[int, dict]] = {}  # userId -> (version, bundle)


def user_dir(user_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", user_id):  # ids become paths; Better Auth ids are alnum
        raise ValueError("bad user id")
    return MODELS_DIR / user_id


def meta(user_id: str) -> dict | None:
    path = user_dir(user_id) / "meta.json"
    return json.loads(path.read_text()) if path.exists() else None


def train(user_id: str, rows: list[dict[str, float]]) -> dict:
    """Fit on enrollment windows and persist. Returns meta.json contents."""
    X = np.array([[r[f] for f in FEATURES] for r in rows], dtype=float)
    medians = np.nanmedian(np.where(np.isnan(X).all(axis=0), 0.0, X), axis=0)  # all-NaN column -> 0
    X = np.where(np.isnan(X), medians, X)

    scaler = StandardScaler().fit(X)
    forest = IsolationForest(n_estimators=200, contamination="auto", random_state=42).fit(scaler.transform(X))
    train_scores = np.sort(forest.decision_function(scaler.transform(X)))

    prev = meta(user_id)
    info = {
        "version": (prev["version"] + 1) if prev else 1,
        "windowCount": len(rows),
        "features": FEATURES,
        "trainedAt": time.time(),
    }
    d = user_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    bundle = {"scaler": scaler, "forest": forest, "medians": medians, "train_scores": train_scores, "features": FEATURES}
    joblib.dump(bundle, d / "model.joblib")
    (d / "meta.json").write_text(json.dumps(info, indent=2))
    with _lock:
        _cache[user_id] = (info["version"], bundle)
    return info


def _load(user_id: str) -> dict | None:
    info = meta(user_id)
    if info is None:
        return None
    with _lock:
        hit = _cache.get(user_id)
        if hit and hit[0] == info["version"]:
            return hit[1]
    bundle = joblib.load(user_dir(user_id) / "model.joblib")
    with _lock:
        _cache[user_id] = (info["version"], bundle)
    return bundle


def window_risk(user_id: str, feats: dict[str, float]) -> float | None:
    """risk = 1 - percentile of this window's IF score within the training scores (lower score = more anomalous).
    None if the user has no model."""
    b = _load(user_id)
    if b is None:
        return None
    x = np.array([[feats.get(f, math.nan) for f in b["features"]]], dtype=float)
    x = np.where(np.isnan(x), b["medians"], x)
    score = b["forest"].decision_function(b["scaler"].transform(x))[0]
    pct = np.searchsorted(b["train_scores"], score, side="right") / len(b["train_scores"])
    return float(np.clip(1.0 - pct, 0.0, 1.0))
