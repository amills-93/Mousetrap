"""Enrollment buffers and the per-user feature log (ARCHITECTURE.md 8.1, 8.3, 8.4).

Enrollment is passive: while a user is enrolling, /ingest sends their windows from normal portal use here instead
of to scoring, and reports `enrollReady` once there is enough to train on. Nuxt then calls /enroll/{id}/finish.
Passive enrollment can span sessions, so it survives an ML restart: `enrolling.json` marks when it started, and
the buffer is rebuilt from the "enroll" rows logged since then.
Every feature vector, enrollment or live, is also appended to models/{userId}/features.parquet.
"""

from __future__ import annotations

import json
import time
from threading import Lock

import pandas as pd

from .features import FEATURES
from .model import MIN_MODALITY_WINDOWS, user_dir

READY_WINDOWS = 40  # total windows before training (model.MIN_WINDOWS is the hard floor)
READY_KEY_WINDOWS = MIN_MODALITY_WINDOWS  # typing decides (Stage 6), so wait until keys can be modeled

_lock = Lock()
_enrolling: dict[str, list[dict[str, float]]] = {}
_logs: dict[str, pd.DataFrame] = {}


def _marker(user_id: str):
    return user_dir(user_id) / "enrolling.json"


def _buf(user_id: str) -> list[dict[str, float]] | None:
    """The user's enrollment buffer, rebuilt from the log after a restart. Call with _lock held."""
    buf = _enrolling.get(user_id)
    if buf is not None:
        return buf
    marker = _marker(user_id)
    if not marker.exists():
        return None
    since = json.loads(marker.read_text())["since"]
    df = _logs.get(user_id)
    path = user_dir(user_id) / "features.parquet"
    if df is None and path.exists():
        df = _logs[user_id] = pd.read_parquet(path)
    buf = []
    if df is not None and len(df):
        buf = df[(df.phase == "enroll") & (df.ts >= since)][FEATURES].to_dict("records")
    _enrolling[user_id] = buf
    return buf


def start(user_id: str) -> None:
    with _lock:
        d = user_dir(user_id)
        d.mkdir(parents=True, exist_ok=True)
        _marker(user_id).write_text(json.dumps({"since": time.time()}))
        _enrolling[user_id] = []


def is_enrolling(user_id: str) -> bool:
    with _lock:
        return _buf(user_id) is not None


def add(user_id: str, rows: list[dict[str, float]]) -> int:
    with _lock:
        buf = _buf(user_id)
        if buf is None:
            return 0
        buf.extend(rows)
        return len(buf)


def count(user_id: str) -> int:
    with _lock:
        return len(_buf(user_id) or ())


def key_count(user_id: str) -> int:
    with _lock:
        return sum(1 for r in _buf(user_id) or () if r.get("has_keys") == 1.0)


def ready(user_id: str) -> bool:
    return count(user_id) >= READY_WINDOWS and key_count(user_id) >= READY_KEY_WINDOWS


def take(user_id: str) -> list[dict[str, float]]:
    """Enrollment windows collected so far; the buffer is kept until finish() succeeds."""
    with _lock:
        return list(_buf(user_id) or ())


def finish(user_id: str) -> None:
    with _lock:
        _enrolling.pop(user_id, None)
        _marker(user_id).unlink(missing_ok=True)


def log_features(user_id: str, session_id: str, phase: str, rows: list[dict[str, float]]) -> None:
    if not rows:
        return
    path = user_dir(user_id) / "features.parquet"
    now = time.time()
    new = pd.DataFrame([{"ts": now, "sessionId": session_id, "phase": phase, **r} for r in rows])
    with _lock:
        df = _logs.get(user_id)
        if df is None:
            df = pd.read_parquet(path) if path.exists() else pd.DataFrame()
        df = pd.concat([df, new], ignore_index=True) if len(df) else new
        _logs[user_id] = df
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
