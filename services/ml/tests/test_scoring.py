import random
import uuid

import pytest

from app import model, scoring
from tests.helpers import batch, mouse, typing
from tests.test_api import H, client, feed, isolated  # noqa: F401  (fixtures)


def enroll(client, user="u1"):
    random.seed(1)
    client.post(f"/enroll/{user}/start", headers=H)
    feed(client, user, "enroll-session", 12)
    r = client.post(f"/enroll/{user}/finish", headers=H).json()
    assert r["ok"], r


def live(client, session, n, typer=typing, mover=mouse, synthetic=0, user="u1"):
    page, t = str(uuid.uuid4()), 0.0
    for seq in range(1, n + 1):
        k, t = typer(t)
        m, t = mover(t)
        r = client.post("/ingest", headers=H, json={
            "userId": user, "sessionId": session, "batch": batch(page, seq, k + m, synthetic=synthetic)})
        assert r.status_code == 200
    return client.get(f"/risk/{session}", headers=H).json()


def impostor_typing(t):
    return typing(t, dwell=35.0, gap=420.0, backspace_every=4)


def impostor_mouse(t):
    return mouse(t, step=30.0, curve=25.0)


def test_unknown_session_has_no_windows(client):
    assert client.get("/risk/nope", headers=H).json() == {
        "risk": 0.0, "windows": 0, "lastUpdated": None, "components": {}, "bot": 0.0}


def test_requires_key(client):
    assert client.get("/risk/s").status_code == 401


def test_not_enrolled_is_not_scored(client):
    assert live(client, "s1", 4)["windows"] == 0


def test_enrollment_is_not_scored(client):
    client.post("/enroll/u1/start", headers=H)
    feed(client, "u1", "s1", 4)
    assert client.get("/risk/s1", headers=H).json()["windows"] == 0


def test_genuine_stays_low_impostor_rises(client):
    enroll(client)
    random.seed(2)
    genuine = live(client, "owner", 8)
    random.seed(3)
    impostor = live(client, "thief", 8, typer=impostor_typing, mover=impostor_mouse)
    assert genuine["windows"] >= 3 and impostor["windows"] >= 3
    assert genuine["risk"] < 0.35 < impostor["risk"], (genuine, impostor)
    assert set(genuine["components"]) == {"keys", "mouse"}
    assert genuine["lastUpdated"] is not None


def test_sessions_are_independent(client):
    enroll(client)
    live(client, "thief", 6, typer=impostor_typing, mover=impostor_mouse)
    random.seed(2)
    assert live(client, "owner", 6)["risk"] < 0.35


def test_synthetic_events_add_risk(client):
    enroll(client)
    random.seed(2)
    clean = live(client, "a", 6)
    random.seed(2)
    bot = live(client, "b", 6, synthetic=3)
    assert bot["risk"] >= clean["risk"] + 0.2
    assert bot["bot"] >= scoring.BOT_SYNTHETIC


def no_events(t):
    return [], t


def test_metronome_typing_is_a_bot(client):
    enroll(client)

    def metronome(t):
        ev = []
        for i in range(30):
            ev += [{"k": "kd", "t": t, "kc": "letter", "code_hash": i % 7},
                   {"k": "ku", "t": t + 50, "kc": "letter", "code_hash": i % 7}]
            t += 100.0
        return ev, t

    assert live(client, "bot", 4, typer=metronome, mover=no_events)["bot"] == scoring.BOT_METRONOME_KEYS


def test_ruler_straight_mouse_is_a_bot(client):
    enroll(client)
    r = live(client, "bot", 4, typer=no_events, mover=lambda t: mouse(t, curve=0.0))
    assert r["bot"] == scoring.BOT_STRAIGHT_MOUSE
    assert live(client, "human", 4, typer=no_events)["bot"] == 0.0


def test_idle_session_expires(client, monkeypatch):
    enroll(client)
    live(client, "s1", 4)
    st = scoring._state["s1"]
    st.last_seen -= scoring.IDLE_TTL_S + 1
    assert client.get("/risk/s1", headers=H).json()["windows"] == 0


def test_combine_weights_mouse_as_weak_evidence():
    assert scoring.combine({}) is None
    assert scoring.combine({"mouse": 1.0}) == pytest.approx(0.4)
    assert scoring.combine({"keys": 1.0}) == 1.0
    assert scoring.combine({"keys": 0.0, "mouse": 1.0}) == pytest.approx(0.4 / 1.4)


def test_calibration_maps_typical_windows_to_zero():
    import numpy as np
    tr = np.linspace(-0.1, 0.1, 100)
    assert model.calibrate(tr, 0.05) == 0.0  # above the 25th percentile
    assert model.calibrate(tr, -1.0) == 1.0  # less typical than every training window
    assert 0 < model.calibrate(tr, -0.08) < 1


def test_train_needs_a_modality(tmp_path):
    rows = [{"has_keys": 0.0, "has_mouse": 0.0, "has_touch": 0.0}] * 30
    with pytest.raises(ValueError):
        model.train("u1", rows)


def test_stage5_model_is_ignored_until_retrained(client):
    enroll(client)
    meta = model.user_dir("u1") / "meta.json"
    meta.write_text(meta.read_text().replace('"format": 2', '"format": 1'))
    model._cache.clear()
    assert model.window_risk("u1", {"has_keys": 1.0}) is None
