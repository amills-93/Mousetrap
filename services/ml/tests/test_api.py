import uuid

import pytest
from fastapi.testclient import TestClient

from app import buffer, enrollment, main, model, scoring
from tests.helpers import batch, mouse, typing

H = {"X-Internal-Key": "test-key"}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(model, "MODELS_DIR", tmp_path)
    buffer._sessions.clear()
    enrollment._enrolling.clear()
    enrollment._logs.clear()
    model._cache.clear()
    scoring._state.clear()
    yield


@pytest.fixture
def client():
    return TestClient(main.app)


def feed(client, user, session, n, page=None, t=0.0, seq0=1):
    page = page or str(uuid.uuid4())
    for seq in range(seq0, seq0 + n):
        k, t = typing(t)
        m, t = mouse(t)
        r = client.post("/ingest", headers=H, json={"userId": user, "sessionId": session, "batch": batch(page, seq, k + m)})
        assert r.status_code == 200, r.text
    return r.json(), t


def test_requires_internal_key(client):
    assert client.get("/users/u1/status").status_code == 401
    assert client.get("/users/u1/status", headers={"X-Internal-Key": "nope"}).status_code == 401
    assert client.get("/healthz").status_code == 200


def test_rejects_path_like_user_ids(client):
    assert client.post("/enroll/..%2Fetc/start", headers=H).status_code in (400, 404)
    assert client.post("/enroll/a.b/start", headers=H).status_code == 400


def test_rejects_key_values(client):
    ev = [{"k": "kd", "t": 1, "kc": "letter", "code_hash": 1, "key": "a"}]
    r = client.post("/ingest", headers=H, json={"userId": "u1", "sessionId": "s", "batch": batch("p", 1, ev)})
    assert r.status_code == 422


def test_full_enrollment(client, tmp_path):
    assert client.get("/users/u1/status", headers=H).json()["enrolled"] is False
    client.post("/enroll/u1/start", headers=H)
    body, _ = feed(client, "u1", "s1", 10)
    assert body["enrollWindows"] >= 20
    r = client.post("/enroll/u1/finish", headers=H).json()
    assert r["ok"] and r["modelVersion"] == 1
    st = client.get("/users/u1/status", headers=H).json()
    assert st["enrolled"] is True and st["enrolling"] is False and st["enrollWindows"] == 0
    assert st["windowCount"] == r["windowCount"] and st["modelVersion"] == 1
    assert {p.name for p in (tmp_path / "u1").iterdir()} == {"model.joblib", "meta.json", "features.parquet", "training.parquet"}


def test_finish_too_early_keeps_enrolling(client):
    client.post("/enroll/u1/start", headers=H)
    feed(client, "u1", "s1", 1)
    r = client.post("/enroll/u1/finish", headers=H).json()
    assert not r["ok"] and "at least" in r["error"]
    assert client.get("/users/u1/status", headers=H).json()["enrolling"] is True
    feed(client, "u1", "s1", 10, seq0=2)
    assert client.post("/enroll/u1/finish", headers=H).json()["ok"]


def test_finish_without_start(client):
    assert client.post("/enroll/u1/finish", headers=H).json()["error"] == "not enrolling"


def test_live_windows_not_counted_as_enrollment(client):
    import pandas as pd
    feed(client, "u1", "s1", 3)
    client.post("/enroll/u1/start", headers=H)
    assert client.get("/users/u1/status", headers=H).json()["enrollWindows"] == 0
    df = pd.read_parquet(model.MODELS_DIR / "u1" / "features.parquet")
    assert set(df["phase"]) == {"live"}


def test_restart_start_resets_buffer(client):
    client.post("/enroll/u1/start", headers=H)
    feed(client, "u1", "s1", 5)
    client.post("/enroll/u1/start", headers=H)
    assert client.get("/users/u1/status", headers=H).json()["enrollWindows"] == 0


def test_enrollment_survives_ml_restart(client):
    """Passive enrollment spans sessions, so the buffer is rebuilt from the feature log after a restart."""
    client.post("/enroll/u1/start", headers=H)
    body, _ = feed(client, "u1", "s1", 5)
    before = body["enrollWindows"]
    enrollment._enrolling.clear()  # simulate process restart
    enrollment._logs.clear()
    st = client.get("/users/u1/status", headers=H).json()
    assert st["enrolling"] is True and st["enrollWindows"] == before
    feed(client, "u1", "s1", 6, seq0=6)
    assert client.post("/enroll/u1/finish", headers=H).json()["ok"]
    enrollment._enrolling.clear()
    assert client.get("/users/u1/status", headers=H).json()["enrolling"] is False


def test_ingest_signals_ready(client):
    body, _ = feed(client, "u1", "s1", 1)
    assert body["enrolled"] is False and body["enrolling"] is False and body["enrollReady"] is False
    client.post("/enroll/u1/start", headers=H)
    body, _ = feed(client, "u1", "s1", 3, seq0=2)
    assert body["enrolling"] is True and body["enrollReady"] is False
    while not body["enrollReady"]:
        body, _ = feed(client, "u1", "s1", 1, seq0=body["enrollWindows"] + 100)
    st = client.get("/users/u1/status", headers=H).json()
    assert st["enrollWindows"] >= st["enrollTarget"] and st["enrollKeyWindows"] >= st["enrollKeyTarget"]
    assert client.post("/enroll/u1/finish", headers=H).json()["ok"]
    body, _ = feed(client, "u1", "s1", 1, seq0=1000)
    assert body["enrolled"] is True and body["enrolling"] is False


def test_mouse_only_is_not_ready(client):
    client.post("/enroll/u1/start", headers=H)
    page, t = str(uuid.uuid4()), 0.0
    for seq in range(1, 40):
        m, t = mouse(t)
        body = client.post("/ingest", headers=H, json={"userId": "u1", "sessionId": "s1", "batch": batch(page, seq, m)}).json()
    assert body["enrollWindows"] >= enrollment.READY_WINDOWS and body["enrollReady"] is False


def test_synthetic_batches_are_not_enrolled(client):
    client.post("/enroll/u1/start", headers=H)
    k, t = typing(0.0)
    m, _ = mouse(t)
    body = client.post("/ingest", headers=H, json={"userId": "u1", "sessionId": "s1", "batch": batch("p", 1, k + m, synthetic=3)}).json()
    assert body["windows"] > 0 and body["enrollWindows"] is None
    assert client.get("/users/u1/status", headers=H).json()["enrollWindows"] == 0


def test_two_tabs_and_two_sessions(client):
    client.post("/enroll/u1/start", headers=H)
    _, t = feed(client, "u1", "s1", 4, page="tab-a")
    feed(client, "u1", "s1", 4, page="tab-b")          # second tab, restarted clock
    feed(client, "u1", "s1", 2, page="tab-a", t=t, seq0=5)  # back to the first tab
    feed(client, "u1", "s2", 4)                        # another browser
    assert client.post("/enroll/u1/finish", headers=H).json()["ok"]


def test_users_are_isolated(client):
    client.post("/enroll/u1/start", headers=H)
    feed(client, "u2", "s9", 5)
    assert client.get("/users/u1/status", headers=H).json()["enrollWindows"] == 0


def test_reenroll_bumps_version_and_scores(client):
    for v in (1, 2):
        client.post("/enroll/u1/start", headers=H)
        feed(client, "u1", "s1", 10)
        assert client.post("/enroll/u1/finish", headers=H).json()["modelVersion"] == v
    import pandas as pd
    rows = pd.read_parquet(model.MODELS_DIR / "u1" / "features.parquet").to_dict("records")
    risks = [model.window_risk("u1", r) for r in rows]
    assert all(0 <= v <= 1 for r in risks for v in r.values())
    assert model.window_risk("nobody", rows[0]) is None


def test_close_scores_the_open_window(client):
    client.post("/enroll/u1/start", headers=H)
    _, t = feed(client, "u1", "s0", 10)
    assert client.post("/enroll/u1/finish", headers=H).json()["ok"]

    page = str(uuid.uuid4())
    k, t = typing(t, n=10)  # 20 events in under 5 s: enough for a window, too few to close it
    r = client.post("/ingest", headers=H, json={"userId": "u1", "sessionId": "s1", "batch": batch(page, 1, k)}).json()
    assert r["windows"] == 0
    assert client.get("/risk/s1", headers=H).json()["windows"] == 0

    r = client.post("/risk/s1/close", headers=H, json={"userId": "u1"})
    assert r.status_code == 200, r.text
    assert r.json()["windows"] == 1
    # Another user's id cannot drain or score this session.
    assert client.post("/risk/s1/close", headers=H, json={"userId": "u2"}).json()["windows"] == 1


def _enrolled(client, user="u1"):
    client.post(f"/enroll/{user}/start", headers=H)
    _, t = feed(client, user, f"{user}-enroll", 10)
    assert client.post(f"/enroll/{user}/finish", headers=H).json()["ok"]
    return t


def test_challenge_collects_keys_after_start(client):
    t = _enrolled(client)
    page = str(uuid.uuid4())
    k, t = typing(t, n=40)  # before the challenge: must not count
    client.post("/ingest", headers=H, json={"userId": "u1", "sessionId": "s1", "batch": batch(page, 1, k)})
    assert client.post("/challenge/s1/start", headers=H, json={"userId": "u1"}).json()["keysModeled"] is True

    r = client.post("/challenge/s1/result", headers=H, json={"userId": "u1"}).json()
    assert (r["started"], r["windows"], r["risk"]) == (True, 0, None)

    k, t = typing(t + 1000, n=20)
    client.post("/ingest", headers=H, json={"userId": "u1", "sessionId": "s1", "batch": batch(page, 2, k)})
    r = client.post("/challenge/s1/result", headers=H, json={"userId": "u1"}).json()
    assert r["windows"] >= 1 and 0.0 <= r["risk"] <= 1.0


def test_challenge_result_without_start_starts_one(client):
    _enrolled(client)
    r = client.post("/challenge/s9/result", headers=H, json={"userId": "u1"}).json()
    assert (r["keysModeled"], r["started"], r["windows"]) == (True, False, 0)
    assert client.post("/challenge/s9/result", headers=H, json={"userId": "u1"}).json()["started"] is True


def test_challenge_without_keys_model(client):
    assert client.post("/challenge/s1/start", headers=H, json={"userId": "nokeys"}).json()["keysModeled"] is False


def test_demo_reset_clears_session_state(client):
    feed(client, "u1", "s1", 3)
    assert buffer.get("s1") is not None
    r = client.post("/demo/reset", headers=H)
    assert r.status_code == 200
    assert buffer.get("s1") is None and scoring.get("s1") is None
    assert client.get("/risk/s1", headers=H).json()["windows"] == 0
    assert client.post("/demo/reset").status_code == 401
