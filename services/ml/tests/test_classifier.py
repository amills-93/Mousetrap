import pytest
from fastapi.testclient import TestClient

from app import classifier, main

H = {"X-Internal-Key": "test-key"}


@pytest.fixture(scope="module", autouse=True)
def trained(tmp_path_factory):
    """Train on the committed synthetic set into a temp dir (a few seconds)."""
    d = tmp_path_factory.mktemp("clf")
    rows = classifier.load_messages()
    import joblib

    joblib.dump(classifier.fit([r["text"] for r in rows], [r["label"] for r in rows], [r["category"] for r in rows]),
                d / "model.joblib")
    old = classifier.CLASSIFIER_DIR
    classifier.CLASSIFIER_DIR, classifier._bundle = d, None
    yield
    classifier.CLASSIFIER_DIR, classifier._bundle = old, None


@pytest.fixture
def client():
    return TestClient(main.app)


def post(client, text):
    r = client.post("/classify", headers=H, json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def test_carrier_pin_scam(client):
    r = post(client, "Nimbus Support: our system upgrade needs your number transfer PIN. Reply with it today.")
    assert r["verdict"] == "scam" and r["accountRisk"] is True
    assert r["category"] in ("port_out_pin", "carrier_impersonation")
    assert "asks_pin" in [f["id"] for f in r["redFlags"]] and r["advice"]


def test_real_carrier_warning_is_not_a_scam(client):
    r = post(client, "Nimbus: reminder, Nimbus will never ask for your transfer PIN or a verification code.")
    assert r["verdict"] == "ok" and r["redFlags"] == [] and r["accountRisk"] is False


def test_real_code_vs_code_theft(client):
    assert post(client, "Your Nimbus verification code is 482913. Don't share it with anyone.")["verdict"] == "ok"
    assert post(client, "Hey it's Riley, I sent my code to your phone by mistake, can you text me the 6 digits?")["verdict"] != "ok"


def test_non_account_scam_has_no_account_risk(client):
    r = post(client, "SwiftShip: your package is held, pay a $2.99 redelivery fee at https://parcel-redeliver.test/x8k2")
    assert r["verdict"] == "scam" and r["accountRisk"] is False


def test_personal_text_ok(client):
    assert post(client, "Running late, save me a seat")["verdict"] == "ok"


def test_negated_requests_are_not_red_flags():
    assert classifier.red_flags("We will never ask you to send your code.") == []
    assert [f["id"] for f in classifier.red_flags("Please send me the code you got.")] == ["asks_code"]


def test_rejects_empty_and_requires_key(client):
    assert client.post("/classify", headers=H, json={"text": ""}).status_code == 422
    assert client.post("/classify", json={"text": "hi"}).status_code == 401
