import json
from pathlib import Path

from fastapi.testclient import TestClient

from mindcare.main import app
from mindcare.schemas import LLMStructuredPayload
from mindcare.session_store import get_session_store


client = TestClient(app)

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "docs" / "TEST_PROMPT_CORPUS.json"
_CORPUS = json.loads(_CORPUS_PATH.read_text())
_CASES = _CORPUS["cases"]


def _payload(message: str) -> dict:
    return {"message": message, "metadata": {"locale": "en-US"}}


def _reset_store() -> None:
    store = get_session_store()
    store._sessions.clear()  # noqa: SLF001
    store._high_risk_counts.clear()  # noqa: SLF001


def test_corpus_medium_and_high_cases_route_without_llm() -> None:
    _reset_store()
    for case in _CASES:
        if case["expected_policy_action"] not in {"medium_template", "high_template"}:
            continue
        resp = client.post("/api/v1/chat", json=_payload(case["input"]))
        assert resp.status_code == 200
        body = resp.json()
        assert body["policy_action"] == case["expected_policy_action"]
        assert "If you are outside the U.S." in body["reply_text"]
        assert body["resources"]


def test_corpus_low_cases_stay_normal_with_mocked_llm(monkeypatch) -> None:
    _reset_store()

    def _fake_ok(_history, latest_user_message):
        assert latest_user_message
        return LLMStructuredPayload(
            reply_text="Low-risk supportive reply.",
            risk_level="low",
            suggested_policy_action="normal",
        )

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", _fake_ok)

    for case in _CASES:
        if case["category"] != "low":
            continue
        resp = client.post("/api/v1/chat", json=_payload(case["input"]))
        assert resp.status_code == 200
        body = resp.json()
        assert body["policy_action"] == "normal"
        assert body["risk_level"] == "low"
        assert body["resources"] == []


def test_parser_failure_returns_contract_fallback_200(monkeypatch) -> None:
    _reset_store()

    def _boom(*_args, **_kwargs):
        raise ValueError("simulated parser failure")

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", _boom)

    resp = client.post("/api/v1/chat", json=_payload("Simulated parser failure case."))
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == "fallback"
    assert body["fallback_reason"] == "llm_parse_failed"
    assert body["risk_level"] == "medium"


def test_three_high_risk_turns_enable_session_lock() -> None:
    _reset_store()
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


def test_post_llm_disallowed_output_is_overridden(monkeypatch) -> None:
    _reset_store()

    def _unsafe_llm(_history, _latest_user_message):
        return LLMStructuredPayload(
            reply_text="Here is step-by-step how to hurt yourself.",
            risk_level="low",
            suggested_policy_action="normal",
        )

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", _unsafe_llm)

    resp = client.post("/api/v1/chat", json=_payload("I am curious about something"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == "high_template"
    assert body["risk_level"] == "high"
    assert body["fallback_reason"] == "post_llm_disallowed_output"
