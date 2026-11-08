"""In-memory per-session event buffers. Windowing and scoring (Stages 5-6) read from here."""

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

from .schemas import TelemetryBatch

MAX_EVENTS = 5000  # ~a few minutes of activity; older events fall off
IDLE_TTL_S = 30 * 60


@dataclass
class SessionBuffer:
    user_id: str
    events: deque = field(default_factory=lambda: deque(maxlen=MAX_EVENTS))
    vw: int = 0
    vh: int = 0
    synthetic: int = 0
    batches: int = 0
    last_seen: float = field(default_factory=time.monotonic)


_sessions: dict[str, SessionBuffer] = {}
_lock = Lock()


def append(user_id: str, session_id: str, batch: TelemetryBatch) -> SessionBuffer:
    now = time.monotonic()
    with _lock:
        for sid in [s for s, b in _sessions.items() if now - b.last_seen > IDLE_TTL_S]:
            del _sessions[sid]
        buf = _sessions.get(session_id)
        if buf is None or buf.user_id != user_id:
            buf = _sessions[session_id] = SessionBuffer(user_id=user_id)
        buf.events.extend(batch.events)
        buf.vw, buf.vh = batch.vw, batch.vh
        buf.synthetic += batch.synthetic
        buf.batches += 1
        buf.last_seen = now
        return buf


def get(session_id: str) -> SessionBuffer | None:
    return _sessions.get(session_id)
