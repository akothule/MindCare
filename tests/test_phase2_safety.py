import json
from pathlib import Path

from fastapi.testclient import TestClient

from mindcare.main import app
from mindcare.schemas import LLMStructuredPayload

client = TestClient(app)

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "docs" / "TEST_PROMPT_CORPUS.json"
_CORPUS = json.loads(_CORPUS_PATH.read_text())
_CASES = _CORPUS["cases"]


def _payload(message: str) -> dict:
    return {"message": message, "metadata": {"locale": "en-US"}}


def test_corpus_high_and_high_policy_cases_route_without_llm() -> None:
    for case in _CASES:
        expected = case["expected_policy_action"]
        if expected not in {"high_template", "high_policy_template"}:
            continue
        resp = client.post("/api/v1/chat", json=_payload(case["input"]))
        assert resp.status_code == 200
        body = resp.json()
        assert body["policy_action"] == expected
        assert "If you are outside the U.S." in body["reply_text"]
        assert body["resources"]
        if expected == "high_policy_template":
            assert "can't help" in body["reply_text"].lower()
        else:
            assert "really glad you shared" in body["reply_text"].lower()


def test_corpus_medium_cases_invoke_llm_with_signals(monkeypatch) -> None:
    calls: list[tuple[str, list[str] | None]] = []

    def _fake(_history: list, msg: str, *, pre_medium_signals=None):
        calls.append((msg, list(pre_medium_signals) if pre_medium_signals else None))
        return LLMStructuredPayload(
            reply_text="I hear how drained you feel.",
            risk_level="medium",
            suggested_policy_action="medium_llm",
        )

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", _fake)

    for case in _CASES:
        if case["expected_policy_action"] != "medium_llm":
            continue
        resp = client.post("/api/v1/chat", json=_payload(case["input"]))
        assert resp.status_code == 200
        body = resp.json()
        assert body["policy_action"] == "medium_llm"
        assert body["risk_level"] == "medium"
        assert "If you are outside the U.S." in body["reply_text"]
        assert body["resources"]
        assert calls[-1][1] is not None
        assert calls[-1][0] == case["input"]


def test_corpus_low_cases_stay_normal_with_mocked_llm(monkeypatch) -> None:
    def _fake_ok(_history, latest_user_message, *, pre_medium_signals=None):
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


def test_pre_medium_merged_into_medium_even_when_model_says_low(monkeypatch) -> None:
    """Heuristic distress + low model risk → still medium_llm so resources stay surfaced."""

    def _fake_llm_reports_low(*_a, **_kw):
        return LLMStructuredPayload(
            reply_text="Sounds really heavy.",
            risk_level="low",
            suggested_policy_action="normal",
        )

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", _fake_llm_reports_low)

    resp = client.post("/api/v1/chat", json=_payload("I feel hopeless about everything lately."))
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_level"] == "medium"
    assert body["policy_action"] == "medium_llm"
    assert body["resources"]
    assert "Sounds really heavy." in body["reply_text"]
    assert "If you are outside the U.S." in body["reply_text"]


def test_parser_failure_returns_contract_fallback_200(monkeypatch) -> None:
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
    def _unsafe_llm(_history, _latest_user_message, *, pre_medium_signals=None):
        return LLMStructuredPayload(
            reply_text="Here is step-by-step how to hurt yourself.",
            risk_level="low",
            suggested_policy_action="normal",
        )

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", _unsafe_llm)

    resp = client.post("/api/v1/chat", json=_payload("I am curious about something"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == "high_policy_template"
    assert body["risk_level"] == "high"
    assert body["fallback_reason"] == "post_llm_disallowed_output"
    assert "can't help" in body["reply_text"].lower()
