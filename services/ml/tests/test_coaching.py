import uuid

import pytest
from fastapi.testclient import TestClient

from app import buffer, coaching, main, scoring
from tests.helpers import batch

H = {"X-Internal-Key": "test-key"}


@pytest.fixture(autouse=True)
def isolated():
    buffer._sessions.clear()
    coaching._state.clear()
    scoring._state.clear()
    yield


@pytest.fixture
def client():
    return TestClient(main.app)


def send(client, events, page, seq, session="s1", user="u1"):
    r = client.post("/ingest", headers=H, json={"userId": user, "sessionId": session, "batch": batch(page, seq, events)})
    assert r.status_code == 200, r.text


def digit(t):
    return [{"k": "kd", "t": t, "kc": "digit", "code_hash": 7}, {"k": "ku", "t": t + 80, "kc": "digit", "code_hash": 7}]


def test_counts_each_signal(client):
    page = str(uuid.uuid4())
    ev = [{"k": "nv", "t": 0, "route": "/security/sim"},
          {"k": "fc", "t": 100, "role": "input:text"},
          {"k": "ps", "t": 200, "role": "input:text"},
          {"k": "vs", "t": 300, "hidden": True}, {"k": "vs", "t": 4300, "hidden": False},  # 4 s away
          {"k": "vs", "t": 4400, "hidden": True}, {"k": "vs", "t": 4900, "hidden": False}]  # 0.5 s blip: ignored
    ev += digit(5000) + digit(5200) + digit(5400)          # a group of three
    ev += digit(8000) + digit(8200)                        # 2.6 s later: chunk
    ev += digit(30000)                                     # 21.8 s later: long pause, too long for a chunk
    send(client, ev, page, 1)
    sig = client.get("/risk/s1", headers=H).json()["coaching"]
    assert sig == {"pastes": 1, "tabSwitches": 1, "longPauses": 1, "chunkedDigits": 1, "navs": 1}


def test_paste_outside_inputs_and_time_away_not_counted(client):
    page = str(uuid.uuid4())
    send(client, [{"k": "ps", "t": 0, "role": "div"}, {"k": "vs", "t": 10, "hidden": True}], page, 1)
    send(client, [{"k": "vs", "t": 60000, "hidden": False}, {"k": "mm", "t": 60010, "x": 1, "y": 1}], page, 2)
    sig = client.get("/risk/s1", headers=H).json()["coaching"]
    assert sig["pastes"] == 0 and sig["longPauses"] == 0 and sig["tabSwitches"] == 1


def test_gaps_measured_within_a_page(client):
    send(client, digit(1000), str(uuid.uuid4()), 1)
    send(client, digit(3000), str(uuid.uuid4()), 1)  # new page: performance.now() restarted
    assert client.get("/risk/s1", headers=H).json()["coaching"]["chunkedDigits"] == 0


def test_unknown_session_reports_zeros(client):
    assert client.get("/risk/nope", headers=H).json()["coaching"] == {
        "pastes": 0, "tabSwitches": 0, "longPauses": 0, "chunkedDigits": 0, "navs": 0}
