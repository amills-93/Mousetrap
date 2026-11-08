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
    assert st == {"enrolled": True, "enrolling": False, "enrollWindows": 0, "windowCount": r["windowCount"], "modelVersion": 1}
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


def test_ml_restart_loses_enrollment(client):
    """In-memory buffer: after a restart status reports not enrolling, so the page asks to start again."""
    client.post("/enroll/u1/start", headers=H)
    feed(client, "u1", "s1", 5)
    enrollment._enrolling.clear()  # simulate process restart
    st = client.get("/users/u1/status", headers=H).json()
    assert st["enrolling"] is False and st["enrollWindows"] == 0


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
