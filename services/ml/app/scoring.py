"""Session risk (ARCHITECTURE.md 8.5): per-window risk, EWMA, bot heuristics, idle expiry.

Each window's modality risks (model.window_risk) are combined into one window risk, weighted by how much each
modality says about identity: risk = sum(w_m * r_m) / max(1, sum(w_m)). Weights below 1 leave room for a zero
prior, so a mouse-only browsing window can contribute at most 0.4 while any window with typing is judged on
its keystrokes. On the Stage 5 data the mouse model does not transfer from the enrollment exercise to
browsing (the owner's own browsing scored ~0.4 on mouse alone), so mouse is weak evidence by design.
"""

import math
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

import numpy as np

from . import model
from .features import Window

ALPHA = 0.3
IDLE_TTL_S = 30 * 60
RECENT_WINDOWS = 20  # kept per session for /feedback

# Keystroke timing separates people best on the Stage 5 data; mouse shape barely does.
WEIGHTS = {"keys": 1.0, "touch": 0.7, "mouse": 0.4}

BOT_SYNTHETIC = 0.3  # untrusted (isTrusted=false) events in the batch
BOT_STRAIGHT_MOUSE = 0.2  # near-zero curvature variance along the mouse path
BOT_METRONOME_KEYS = 0.3  # inter-key interval std < 5 ms over 20+ keys
STRAIGHT_ANGLE_STD = 0.01  # rad
METRONOME_STD_MS = 5.0
METRONOME_MIN_KEYS = 20


@dataclass
class SessionRisk:
    user_id: str
    risk: float = 0.0
    windows: int = 0
    last_updated: float | None = None  # unix seconds
    components: dict[str, float] = field(default_factory=dict)  # per-modality EWMA
    bot: float = 0.0  # last window's bot penalty
    recent: deque = field(default_factory=lambda: deque(maxlen=RECENT_WINDOWS))  # feature rows, bot-free
    pending_synthetic: bool = False  # synthetic events in a batch that completed no window yet
    last_seen: float = field(default_factory=time.monotonic)
    # Step-up typing challenge: keys risk (+ bot penalty) of each window since it started; None when not running.
    challenge: list[float] | None = None


_state: dict[str, SessionRisk] = {}
_lock = Lock()


def bot_penalty(window: Window, feats: dict[str, float], synthetic: bool) -> float:
    p = BOT_SYNTHETIC if synthetic else 0.0
    if feats.get("has_mouse") == 1.0 and feats.get("angle_std", math.nan) < STRAIGHT_ANGLE_STD:
        p += BOT_STRAIGHT_MOUSE
    kd = [e.t for e in window if e.k == "kd"]
    if len(kd) >= METRONOME_MIN_KEYS and float(np.std(np.diff(kd))) < METRONOME_STD_MS:
        p += BOT_METRONOME_KEYS
    return p


def combine(mod_risks: dict[str, float]) -> float | None:
    """Window risk from per-modality risks; None if the window has no modality this user has a model for."""
    if not mod_risks:
        return None
    total = sum(WEIGHTS[m] for m in mod_risks)
    return sum(WEIGHTS[m] * r for m, r in mod_risks.items()) / max(1.0, total)


def _ewma(prev: float | None, x: float, alpha: float) -> float:
    return x if prev is None else alpha * x + (1 - alpha) * prev


def update(user_id: str, session_id: str, windows: list[Window], rows: list[dict[str, float]], synthetic: int) -> SessionRisk | None:
    """Score this batch's completed windows into the session. None if the user has no model."""
    now = time.monotonic()
    with _lock:
        for sid in [s for s, st in _state.items() if now - st.last_seen > IDLE_TTL_S]:
            del _state[sid]
        st = _state.get(session_id)
        if st is None or st.user_id != user_id:
            st = _state[session_id] = SessionRisk(user_id=user_id)
        st.last_seen = now
        flagged = st.pending_synthetic or synthetic > 0
        st.pending_synthetic = flagged and not windows

        for window, feats in zip(windows, rows):
            mod_risks = model.window_risk(user_id, feats)
            if mod_risks is None:
                return None
            bot = bot_penalty(window, feats, flagged)
            if st.challenge is not None and "keys" in mod_risks:
                st.challenge.append(min(1.0, mod_risks["keys"] + bot))
            risk = combine(mod_risks)
            if risk is None and not bot:
                continue
            risk = min(1.0, (risk or 0.0) + bot)
            st.risk = _ewma(st.risk if st.windows else None, risk, ALPHA)
            for m, r in mod_risks.items():
                st.components[m] = _ewma(st.components.get(m), r, ALPHA)
            st.bot = bot
            if not bot:
                st.recent.append(feats)
            st.windows += 1
            st.last_updated = time.time()
        return st


def get(session_id: str) -> SessionRisk | None:
    st = _state.get(session_id)
    if st is not None and time.monotonic() - st.last_seen > IDLE_TTL_S:
        return None
    return st


def start_challenge(user_id: str, session_id: str) -> None:
    """Begin collecting keystroke risk for a step-up typing challenge (restarts one already running)."""
    with _lock:
        st = _state.get(session_id)
        if st is None or st.user_id != user_id:
            st = _state[session_id] = SessionRisk(user_id=user_id)
        st.last_seen = time.monotonic()
        st.challenge = []


def challenge(session_id: str, user_id: str) -> list[float] | None:
    with _lock:
        st = _state.get(session_id)
        return None if st is None or st.user_id != user_id or st.challenge is None else list(st.challenge)


def take_recent(session_id: str, user_id: str) -> list[dict[str, float]]:
    """Recent windows of a session after a successful step-up; resets its score, since the user just proved
    who they are. The windows stay counted, so policy keeps judging the session normally afterwards."""
    with _lock:
        st = _state.get(session_id)
        if st is None or st.user_id != user_id:
            return []
        rows = list(st.recent)
        st.recent.clear()
        st.risk = 0.0
        st.components = {m: 0.0 for m in st.components}
        st.bot = 0.0
        return rows
