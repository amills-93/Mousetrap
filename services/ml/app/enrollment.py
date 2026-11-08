"""Enrollment buffers and the per-user feature log (ARCHITECTURE.md 8.1, 8.3).

While a user is enrolling, /ingest sends their windows here instead of to scoring.
Every feature vector, enrollment or live, is also appended to models/{userId}/features.parquet.
"""

from __future__ import annotations

import time
from threading import Lock

import pandas as pd

from .model import user_dir

_lock = Lock()
_enrolling: dict[str, list[dict[str, float]]] = {}
_logs: dict[str, pd.DataFrame] = {}


def start(user_id: str) -> None:
    with _lock:
        _enrolling[user_id] = []


def is_enrolling(user_id: str) -> bool:
    return user_id in _enrolling


def add(user_id: str, rows: list[dict[str, float]]) -> int:
    with _lock:
        buf = _enrolling.get(user_id)
        if buf is None:
            return 0
        buf.extend(rows)
        return len(buf)


def count(user_id: str) -> int:
    return len(_enrolling.get(user_id, ()))


def take(user_id: str) -> list[dict[str, float]]:
    """Enrollment windows collected so far; the buffer is kept until finish() succeeds."""
    with _lock:
        return list(_enrolling.get(user_id, ()))


def finish(user_id: str) -> None:
    with _lock:
        _enrolling.pop(user_id, None)


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
