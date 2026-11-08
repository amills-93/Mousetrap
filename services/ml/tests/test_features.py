import math

import pytest

from app import features
from app.features import FEATURES, Windower, extract, normalize
from app.schemas import TelemetryBatch
from tests.helpers import batch, mouse, swipe, tap, typing, wheel


def evs(events, vw=1280, vh=800):
    return normalize(TelemetryBatch(**batch("p", 1, events, vw, vh)).events, vw, vh)


# --- windowing

def test_event_cap_and_overlap():
    w = Windower()
    out = w.push("p", evs([{"k": "mm", "t": i * 20.0, "x": i, "y": 0} for i in range(150)]))
    assert [len(x) for x in out] == [60, 60, 60, 60]
    assert out[1][0].t == out[0][30].t  # 50% overlap


def test_time_cap_waits_for_next_event():
    w = Windower()
    slow = [{"k": "mm", "t": i * 200.0, "x": i, "y": 0} for i in range(20)]  # 20 events over 3.8 s
    assert w.push("p", evs(slow)) == []  # window still open
    out = w.push("p", evs([{"k": "mm", "t": 5100.0, "x": 0, "y": 0}]))
    assert len(out) == 1 and len(out[0]) == 20 and out[0][-1].t < 5000


def test_idle_windows_discarded():
    w = Windower()
    sparse = [{"k": "mm", "t": i * 1000.0, "x": i, "y": 0} for i in range(30)]
    assert w.push("p", evs(sparse)) == []


def test_new_page_drains_and_resets_timeline():
    w = Windower()
    w.push("a", evs([{"k": "mm", "t": 10000 + i * 20.0, "x": i, "y": 0} for i in range(20)]))
    out = w.push("b", evs([{"k": "mm", "t": i * 20.0, "x": i, "y": 0} for i in range(5)]))
    assert len(out) == 1 and all(e.t >= 10000 for e in out[0])  # old page closed, not mixed with new t
    assert all(e.t < 10000 for e in w.pending)


def test_drain_respects_minimum():
    w = Windower()
    w.push("p", evs([{"k": "mm", "t": i * 20.0, "x": i, "y": 0} for i in range(10)]))
    assert w.drain() == []


def test_focus_and_nav_dropped():
    out = evs([{"k": "fc", "t": 1.0, "role": "text"}, {"k": "nv", "t": 2.0, "route": "/x"}])
    assert out == []


# --- features

def test_all_features_present_and_flags():
    ev, _ = typing(0)
    f = extract(evs(ev))
    assert list(f) == FEATURES
    assert f["has_keys"] == 1 and f["has_mouse"] == 0 and f["has_touch"] == 0
    assert all(math.isnan(f[k]) for k in features.MOUSE_FEATURES + features.TOUCH_FEATURES)


def test_keystroke_values():
    ev, _ = typing(0, n=20, dwell=90, gap=150, backspace_every=4)
    f = extract(evs(ev))
    assert 90 <= f["dwell_mean"] <= 100
    assert 50 <= f["flight_mean"] <= 100  # gap - dwell
    assert f["backspace_ratio"] == pytest.approx(5 / 20)
    assert 5 < f["typing_rate"] < 7.5


def test_too_few_key_pairs_is_missing():
    ev, _ = typing(0, n=3)
    assert extract(evs(ev))["has_keys"] == 0


def test_mouse_values_and_click_hold():
    ev, _ = mouse(0)
    f = extract(evs(ev))
    assert f["has_mouse"] == 1
    assert 0.9 < f["straightness"] <= 1.0
    assert f["click_hold_mean"] == pytest.approx(100)
    assert f["speed_mean"] > 0 and f["pause_count"] == 0


def test_pauses_split_segments():
    ev = [{"k": "mm", "t": i * 20.0 + (400 if i >= 10 else 0), "x": i * 5, "y": 0} for i in range(20)]
    f = extract(evs(ev))
    assert f["pause_count"] == 1 and f["pause_mean"] == pytest.approx(420)


def test_speed_normalized_by_viewport():
    ev, _ = mouse(0)
    small = extract(evs(ev, 640, 400))["speed_mean"]
    big = extract(evs(ev, 1280, 800))["speed_mean"]
    assert small == pytest.approx(2 * big)


def test_wheel():
    m, t = mouse(0)
    w, _ = wheel(t, n=9, flip_every=3)
    f = extract(evs(m + w))
    assert f["scroll_dir_changes"] == 2
    assert f["scroll_rate"] > 0


def test_touch_taps_and_swipes():
    ev, t = [], 0.0
    for i in range(3):
        e, t = tap(t, i, dur=80, r=10)
        ev += e
        t += 300
    for i in range(3, 6):
        e, t = swipe(t, i, dy=-300, dur=240, r=14)
        ev += e
        t += 300
    f = extract(evs(ev, 400, 800))
    assert f["has_touch"] == 1
    assert f["tap_dur_mean"] == pytest.approx(80)
    assert f["swipe_dur"] == pytest.approx(240)
    assert f["swipe_straightness"] == pytest.approx(1.0)
    assert f["swipe_dir_share"] == 1.0
    assert f["gesture_gap_mean"] == pytest.approx(300)
    assert 10 < f["touch_radius_mean"] < 14
    assert math.isnan(f["touch_force_mean"])  # force always 0 -> skipped


def test_touch_force_when_supported():
    ev, t = [], 0.0
    for i in range(3):
        e, t = tap(t, i, f=0.5)
        ev += e
        t += 200
    assert extract(evs(ev))["touch_force_mean"] == pytest.approx(0.5)


def test_touch_needs_three_gestures():
    ev, t = tap(0, 1)
    ev2, _ = tap(t + 100, 2)
    assert extract(evs(ev + ev2))["has_touch"] == 0


def test_unterminated_gesture_ignored():
    ev, t = [], 0.0
    for i in range(3):
        e, t = tap(t, i)
        ev += e
        t += 200
    ev.append({"k": "ts", "t": t, "id": 9, "x": 0, "y": 0, "r": 5, "f": 0})
    assert extract(evs(ev))["has_touch"] == 1
