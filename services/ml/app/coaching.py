"""Signs that someone is being talked through an action (ARCHITECTURE.md 8.6): rules over the raw event stream,
no model and no per-user profile. ML only counts what it sees; Nuxt's policy turns the counts into a score.

- pastes: a paste into an input (e.g. a code or ICCID read from a message)
- tab switches: left the page for 1.5 s+ and came back (checking a text, another app)
- long pauses: 10 s+ with no input while the page was visible (listening to instructions)
- chunked digits: digits typed in groups with 1.2-8 s gaps between them (being read out a few at a time)
- navs: route changes this session (going straight to a critical page means few of them)

Timestamps from the browser are per page (performance.now), so gaps are measured within a page; recency uses the
server's own clock when the batch arrived.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

RECENT_S = 180  # counts cover the last 3 minutes
AWAY_MIN_MS = 1500
PAUSE_MIN_MS = 10_000
PAUSE_MAX_MS = 120_000  # longer is "walked away", not "listening"
CHUNK_GAP_MS = (1200, 8000)
IDLE_TTL_S = 30 * 60
SIGNALS = ("pastes", "tabSwitches", "longPauses", "chunkedDigits")


@dataclass
class _Page:
    last_t: float | None = None  # last event time, any kind
    away_since: float | None = None
    last_digit: float | None = None


@dataclass
class _Session:
    user_id: str
    seen: dict[str, deque] = field(default_factory=lambda: {s: deque(maxlen=50) for s in SIGNALS})
    navs: int = 0
    pages: dict[str, _Page] = field(default_factory=dict)
    last_seen: float = field(default_factory=time.monotonic)


_state: dict[str, _Session] = {}
_lock = Lock()


def observe(user_id: str, session_id: str, page_id: str, events: list) -> None:
    now = time.monotonic()
    with _lock:
        for sid in [s for s, st in _state.items() if now - st.last_seen > IDLE_TTL_S]:
            del _state[sid]
        st = _state.get(session_id)
        if st is None or st.user_id != user_id:
            st = _state[session_id] = _Session(user_id=user_id)
        st.last_seen = now
        page = st.pages.setdefault(page_id, _Page())
        if len(st.pages) > 20:  # keep the newest few pages
            for old in list(st.pages)[:-20]:
                del st.pages[old]

        for e in sorted(events, key=lambda e: e.t):
            if page.last_t is not None and page.away_since is None:
                gap = e.t - page.last_t
                if PAUSE_MIN_MS <= gap <= PAUSE_MAX_MS:
                    st.seen["longPauses"].append(now)
            page.last_t = e.t

            if e.k == "ps" and e.role.startswith("input"):
                st.seen["pastes"].append(now)
            elif e.k == "vs":
                if e.hidden:
                    page.away_since = e.t
                elif page.away_since is not None:
                    if e.t - page.away_since >= AWAY_MIN_MS:
                        st.seen["tabSwitches"].append(now)
                    page.away_since = None
            elif e.k == "nv":
                st.navs += 1
            elif e.k == "kd":
                if e.kc == "digit":
                    if page.last_digit is not None and CHUNK_GAP_MS[0] <= e.t - page.last_digit <= CHUNK_GAP_MS[1]:
                        st.seen["chunkedDigits"].append(now)
                    page.last_digit = e.t
                elif e.kc not in ("modifier", "backspace"):
                    page.last_digit = None


def signals(session_id: str) -> dict[str, int]:
    """Counts over the last RECENT_S seconds, plus total navs this session. All zero for an unknown session."""
    now = time.monotonic()
    with _lock:
        st = _state.get(session_id)
        if st is None:
            return {**{s: 0 for s in SIGNALS}, "navs": 0}
        out = {s: sum(1 for ts in st.seen[s] if now - ts <= RECENT_S) for s in SIGNALS}
        out["navs"] = st.navs
        return out
