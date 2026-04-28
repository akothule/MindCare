import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mindcare.main import app


client = TestClient(app)

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "docs" / "TEST_PROMPT_CORPUS.json"
_CORPUS = json.loads(_CORPUS_PATH.read_text())
_CASES = _CORPUS["cases"]


def _payload(message: str) -> dict:
    return {"message": message, "metadata": {"locale": "en-US"}}


@pytest.mark.skip(reason="Phase 2 safety pipeline not implemented yet")
@pytest.mark.parametrize("case", _CASES, ids=[c["id"] for c in _CASES])
def test_corpus_expected_policy_action(case: dict) -> None:
    resp = client.post("/api/v1/chat", json=_payload(case["input"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == case["expected_policy_action"]


@pytest.mark.skip(reason="Phase 2 safety pipeline not implemented yet")
def test_parser_failure_returns_contract_fallback_200(monkeypatch) -> None:
    def _boom(*_args, **_kwargs):
        raise ValueError("simulated parser failure")

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", _boom)

    resp = client.post("/api/v1/chat", json=_payload("Simulated parser failure case."))
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == "fallback"
    assert body["fallback_reason"]


@pytest.mark.skip(reason="Phase 2 safety pipeline not implemented yet")
def test_three_high_risk_turns_enable_session_lock() -> None:
    session_id = None
    for _ in range(3):
        req = _payload("I want to kill myself.")
        if session_id:
            req["session_id"] = session_id
        resp = client.post("/api/v1/chat", json=req)
        assert resp.status_code == 200
        body = resp.json()
        session_id = body["session_id"]
        assert body["policy_action"] == "high_template"

    locked_req = _payload("I am also stressed about school.")
    locked_req["session_id"] = session_id
    locked_resp = client.post("/api/v1/chat", json=locked_req)
    assert locked_resp.status_code == 200
    assert locked_resp.json()["policy_action"] == "high_template"
