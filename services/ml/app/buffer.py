"""In-memory per-session state: recent raw events plus the windower that turns them into windows."""

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

from .features import Window, Windower, normalize
from .schemas import TelemetryBatch

MAX_EVENTS = 5000  # ~a few minutes of activity; older events fall off
IDLE_TTL_S = 30 * 60


@dataclass
class SessionBuffer:
    user_id: str
    events: deque = field(default_factory=lambda: deque(maxlen=MAX_EVENTS))
    windower: Windower = field(default_factory=Windower)
    synthetic: int = 0
    batches: int = 0
    last_seen: float = field(default_factory=time.monotonic)


_sessions: dict[str, SessionBuffer] = {}
_lock = Lock()


def append(user_id: str, session_id: str, batch: TelemetryBatch) -> tuple[SessionBuffer, list[Window]]:
    """Buffer a batch and return any windows it completed."""
    now = time.monotonic()
    with _lock:
        for sid in [s for s, b in _sessions.items() if now - b.last_seen > IDLE_TTL_S]:
            del _sessions[sid]
        buf = _sessions.get(session_id)
        if buf is None or buf.user_id != user_id:
            buf = _sessions[session_id] = SessionBuffer(user_id=user_id)
        buf.events.extend(batch.events)
        windows = buf.windower.push(batch.pageId, normalize(batch.events, batch.vw, batch.vh))
        buf.synthetic += batch.synthetic
        buf.batches += 1
        buf.last_seen = now
        return buf, windows


def get(session_id: str) -> SessionBuffer | None:
    return _sessions.get(session_id)



def drain_user(user_id: str) -> list[Window]:
    """Close the open window of every session belonging to this user (used at enrollment finish)."""
    with _lock:
        return [w for b in _sessions.values() if b.user_id == user_id for w in b.windower.drain()]
