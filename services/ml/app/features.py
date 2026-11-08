"""Windowing (ARCHITECTURE.md 8.2) and per-window features (8.3).

Events arrive as pydantic models from schemas.py. Coordinates are normalized by max(vw, vh) at ingest so
angles survive and speeds are comparable across window sizes. Missing modalities yield NaN features plus a
0 has_* flag; model.py imputes NaNs with the user's enrollment medians.
"""

import math
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

WINDOW_MS = 5000
WINDOW_MAX_EVENTS = 60
WINDOW_MIN_EVENTS = 15
PAUSE_MS = 150
TAP_MAX_PX = 10

MIN_KEY_PAIRS = 4
MIN_MOVES = 10
MIN_GESTURES = 3

KEY_FEATURES = [
    "dwell_mean", "dwell_std", "dwell_median", "dwell_p90",
    "flight_mean", "flight_std", "flight_median", "flight_p90",
    "digraph_mean", "backspace_ratio", "typing_rate",
]
MOUSE_FEATURES = [
    "speed_mean", "speed_std", "speed_p90",
    "accel_mean", "accel_std",
    "straightness",
    "angle_mean", "angle_std",
    "pause_count", "pause_mean",
    "click_hold_mean", "click_hold_std",
    "scroll_rate", "scroll_dir_changes",
]
TOUCH_FEATURES = [
    "tap_dur_mean", "tap_dur_std",
    "swipe_len", "swipe_dur", "swipe_speed_mean", "swipe_speed_p90", "swipe_straightness", "swipe_dir_share",
    "touch_radius_mean", "touch_radius_std", "touch_force_mean", "touch_force_std",
    "gesture_gap_mean", "gesture_gap_std",
]
FLAGS = ["has_keys", "has_mouse", "has_touch"]
FEATURES = KEY_FEATURES + MOUSE_FEATURES + TOUCH_FEATURES + FLAGS


@dataclass(frozen=True, slots=True)
class Ev:
    """One collector event with coordinates normalized to the viewport (and raw px kept for tap travel)."""

    k: str
    t: float
    x: float = 0.0
    y: float = 0.0
    px: float = 0.0  # px per normalized unit, i.e. max(vw, vh)
    kc: str = ""
    code: int = 0
    b: int = 0
    dy: float = 0.0
    id: int = 0
    r: float = 0.0
    f: float = 0.0


def normalize(events, vw: int, vh: int) -> list[Ev]:
    scale = float(max(vw, vh, 1))
    out = []
    for e in events:
        d = e.model_dump()
        k = d.pop("k")
        if k in ("fc", "nv"):
            continue  # focus/route changes carry no timing signal we model
        if "x" in d:
            d["x"] /= scale
            d["y"] /= scale
            d["px"] = scale
        if "code_hash" in d:
            d["code"] = d.pop("code_hash")
        out.append(Ev(k=k, **d))
    return out


Window = list[Ev]


@dataclass
class Windower:
    """Streaming 5 s / 60-event windows with 50% overlap. Feed batches with push(); it returns finished windows."""

    pending: list[Ev] = field(default_factory=list)
    page_id: str | None = None

    def push(self, page_id: str, events: list[Ev]) -> list[list[Ev]]:
        out: list[list[Ev]] = []
        if page_id != self.page_id:  # new page load: performance.now() restarted, so don't mix timelines
            out += self.drain()
            self.page_id = page_id
        self.pending.extend(events)
        while self.pending:
            start = self.pending[0].t
            end = 0
            while end < len(self.pending) and end < WINDOW_MAX_EVENTS and self.pending[end].t < start + WINDOW_MS:
                end += 1
            if end == len(self.pending) and end < WINDOW_MAX_EVENTS:
                break  # window still open: wait for more events
            window = self.pending[:end]
            if len(window) >= WINDOW_MIN_EVENTS:
                out.append(window)
            self.pending = self.pending[max(1, end // 2):]
        return out

    def drain(self) -> list[list[Ev]]:
        """Close out the open window (page change, enrollment finish)."""
        window, self.pending = self.pending, []
        return [window] if len(window) >= WINDOW_MIN_EVENTS else []


def _stats(xs, *names) -> dict[str, float]:
    a = np.asarray(xs, dtype=float)
    fns = {
        "mean": np.mean, "std": np.std, "median": np.median,
        "p90": lambda v: np.percentile(v, 90),
    }
    return {n: float(fns[n](a)) if a.size else math.nan for n in names}


def _keys(evs: list[Ev], duration_s: float) -> dict[str, float]:
    keys = [e for e in evs if e.k in ("kd", "ku")]
    down: dict[int, Ev] = {}
    pairs: list[tuple[Ev, Ev]] = []  # (kd, ku) of the same physical key
    for e in keys:
        if e.k == "kd":
            down[e.code] = e
        elif e.code in down:
            pairs.append((down.pop(e.code), e))
    if len(pairs) < MIN_KEY_PAIRS:
        return {f: math.nan for f in KEY_FEATURES} | {"has_keys": 0.0}

    pairs.sort(key=lambda p: p[0].t)
    dwell = [u.t - d.t for d, u in pairs]
    flight = [b[0].t - a[1].t for a, b in zip(pairs, pairs[1:])]  # keyup -> next keydown (negative = rollover)

    # Digraph latency (kd -> next kd) for code_hash pairs that recur in the window; all pairs if none recur.
    digraphs = [((a[0].code, b[0].code), b[0].t - a[0].t) for a, b in zip(pairs, pairs[1:])]
    counts = Counter(p for p, _ in digraphs)
    recurring = [lat for p, lat in digraphs if counts[p] > 1] or [lat for _, lat in digraphs]

    s_dwell = _stats(dwell, "mean", "std", "median", "p90")
    s_flight = _stats(flight, "mean", "std", "median", "p90")
    kds = [e for e in keys if e.k == "kd"]
    return {
        **{f"dwell_{n}": v for n, v in s_dwell.items()},
        **{f"flight_{n}": v for n, v in s_flight.items()},
        "digraph_mean": _stats(recurring, "mean")["mean"],
        "backspace_ratio": sum(e.kc == "backspace" for e in kds) / len(kds),
        "typing_rate": len(kds) / duration_s,
        "has_keys": 1.0,
    }


def _mouse(evs: list[Ev], duration_s: float) -> dict[str, float]:
    moves = [e for e in evs if e.k == "mm"]
    if len(moves) < MIN_MOVES:
        return {f: math.nan for f in MOUSE_FEATURES} | {"has_mouse": 0.0}

    speeds, accels, angles, pauses = [], [], [], []
    segments: list[list[Ev]] = [[moves[0]]]
    prev_speed = prev_angle = None
    for a, b in zip(moves, moves[1:]):
        dt = b.t - a.t
        if dt > PAUSE_MS:
            pauses.append(dt)
            segments.append([b])
            prev_speed = prev_angle = None
            continue
        segments[-1].append(b)
        dx, dy = b.x - a.x, b.y - a.y
        dist = math.hypot(dx, dy)
        if dt <= 0:
            continue
        v = dist / (dt / 1000)  # viewport units per second
        speeds.append(v)
        if prev_speed is not None:
            accels.append((v - prev_speed) / (dt / 1000))
        prev_speed = v
        if dist > 0:
            ang = math.atan2(dy, dx)
            if prev_angle is not None:
                d = abs(ang - prev_angle)
                angles.append(min(d, 2 * math.pi - d))
            prev_angle = ang

    straight = []
    for seg in segments:
        if len(seg) < 3:
            continue
        path = sum(math.hypot(b.x - a.x, b.y - a.y) for a, b in zip(seg, seg[1:]))
        if path > 0:
            straight.append(math.hypot(seg[-1].x - seg[0].x, seg[-1].y - seg[0].y) / path)

    holds, down = [], {}
    for e in evs:
        if e.k == "md":
            down[e.b] = e.t
        elif e.k == "mu" and e.b in down:
            holds.append(e.t - down.pop(e.b))

    wheel = [e.dy for e in evs if e.k == "wh" and e.dy != 0]
    dir_changes = sum((a > 0) != (b > 0) for a, b in zip(wheel, wheel[1:]))

    s_speed = _stats(speeds, "mean", "std", "p90")
    s_accel = _stats(np.abs(accels), "mean", "std")
    s_angle = _stats(angles, "mean", "std")
    s_hold = _stats(holds, "mean", "std")
    return {
        **{f"speed_{n}": v for n, v in s_speed.items()},
        **{f"accel_{n}": v for n, v in s_accel.items()},
        "straightness": _stats(straight, "mean")["mean"],
        **{f"angle_{n}": v for n, v in s_angle.items()},
        "pause_count": float(len(pauses)),
        "pause_mean": _stats(pauses, "mean")["mean"] if pauses else 0.0,
        **{f"click_hold_{n}": v for n, v in s_hold.items()},
        "scroll_rate": len(wheel) / duration_s,
        "scroll_dir_changes": float(dir_changes),
        "has_mouse": 1.0,
    }


def _touch(evs: list[Ev]) -> dict[str, float]:
    open_: dict[int, list[Ev]] = {}
    gestures: list[list[Ev]] = []
    for e in evs:
        if e.k == "ts":
            open_[e.id] = [e]
        elif e.id in open_:
            open_[e.id].append(e)
            if e.k == "te":
                gestures.append(open_.pop(e.id))
    if len(gestures) < MIN_GESTURES:
        return {f: math.nan for f in TOUCH_FEATURES} | {"has_touch": 0.0}

    gestures.sort(key=lambda g: g[0].t)
    taps, swipes = [], []
    for g in gestures:
        s, e = g[0], g[-1]
        travel_px = math.hypot(e.x - s.x, e.y - s.y) * s.px
        (taps if travel_px < TAP_MAX_PX else swipes).append(g)

    tap_dur = [g[-1].t - g[0].t for g in taps]
    s_len, s_dur, s_speed, s_straight, dirs = [], [], [], [], []
    for g in swipes:
        s, e = g[0], g[-1]
        dx, dy = e.x - s.x, e.y - s.y
        length = math.hypot(dx, dy)
        path = sum(math.hypot(b.x - a.x, b.y - a.y) for a, b in zip(g, g[1:]))
        dur = max(e.t - s.t, 1.0)
        s_len.append(length)
        s_dur.append(dur)
        s_speed.append(length / (dur / 1000))
        s_straight.append(length / path if path > 0 else 1.0)
        dirs.append(("R" if dx > 0 else "L") if abs(dx) >= abs(dy) else ("D" if dy > 0 else "U"))

    points = [e for g in gestures for e in g]
    forces = [e.f for e in points]
    gaps = [b[0].t - a[-1].t for a, b in zip(gestures, gestures[1:])]
    s_tap = _stats(tap_dur, "mean", "std")
    s_sp = _stats(s_speed, "mean", "p90")
    s_r = _stats([e.r for e in points], "mean", "std")
    s_f = _stats(forces, "mean", "std") if any(forces) else {"mean": math.nan, "std": math.nan}
    s_gap = _stats(gaps, "mean", "std")
    return {
        "tap_dur_mean": s_tap["mean"], "tap_dur_std": s_tap["std"],
        "swipe_len": _stats(s_len, "mean")["mean"],
        "swipe_dur": _stats(s_dur, "mean")["mean"],
        "swipe_speed_mean": s_sp["mean"], "swipe_speed_p90": s_sp["p90"],
        "swipe_straightness": _stats(s_straight, "mean")["mean"],
        "swipe_dir_share": max(Counter(dirs).values()) / len(dirs) if dirs else math.nan,
        "touch_radius_mean": s_r["mean"], "touch_radius_std": s_r["std"],
        "touch_force_mean": s_f["mean"], "touch_force_std": s_f["std"],
        "gesture_gap_mean": s_gap["mean"], "gesture_gap_std": s_gap["std"],
        "has_touch": 1.0,
    }


def extract(window: Window) -> dict[str, float]:
    """Feature dict with every name in FEATURES; NaN where a modality (or sub-feature) has no data."""
    duration_s = max((window[-1].t - window[0].t) / 1000, 0.5)
    feats = {**_keys(window, duration_s), **_mouse(window, duration_s), **_touch(window)}
    return {f: feats[f] for f in FEATURES}
