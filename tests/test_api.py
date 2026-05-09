from fastapi.testclient import TestClient

from mindcare.main import app
from mindcare.schemas import LLMStructuredPayload


client = TestClient(app)


def test_health_endpoints_return_ok() -> None:
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert root_resp.json() == {"status": "ok", "service": "mindcare"}

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json() == {"status": "ok", "service": "mindcare"}


def test_chat_rejects_empty_message() -> None:
    resp = client.post("/api/v1/chat", json={"message": "   "})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "message must not be empty"


def test_chat_rejects_too_long_message() -> None:
    resp = client.post("/api/v1/chat", json={"message": "x" * 2001})
    assert resp.status_code == 400
    assert "maximum length of 2000" in resp.json()["detail"]


def test_chat_returns_contract_fields(monkeypatch) -> None:
    def fake_complete_chat_turn(history, latest_user_message, *, pre_medium_signals=None):
        assert latest_user_message == "I feel stressed today"
        return LLMStructuredPayload(
            reply_text="Thanks for sharing. I'm here with you.",
            risk_level="low",
            suggested_policy_action="normal",
        )

    monkeypatch.setattr(
        "mindcare.routers.chat.complete_chat_turn",
        fake_complete_chat_turn,
    )

    resp = client.post("/api/v1/chat", json={"message": "I feel stressed today"})
    assert resp.status_code == 200

    body = resp.json()
    assert body["session_id"]
    assert body["request_id"]
    assert body["reply_text"] == "Thanks for sharing. I'm here with you."
    assert body["risk_level"] == "low"
    assert body["policy_action"] == "normal"
    assert body["resources"] == []
    assert body["fallback_reason"] is None
    assert isinstance(body["latency_ms"], int)


def test_chat_high_risk_uses_fixed_template() -> None:
    resp = client.post("/api/v1/chat", json={"message": "I want to kill myself."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_level"] == "high"
    assert body["policy_action"] == "high_template"
    assert "Call or text **988**" in body["reply_text"]
    assert "If you are outside the U.S." in body["reply_text"]
    assert body["resources"]


def test_chat_parser_failure_returns_fallback_200(monkeypatch) -> None:
    def fake_complete_chat_turn(_history, _latest_user_message, *, pre_medium_signals=None):
        raise ValueError("simulated parser failure")

    monkeypatch.setattr(
        "mindcare.routers.chat.complete_chat_turn",
        fake_complete_chat_turn,
    )

    resp = client.post("/api/v1/chat", json={"message": "I feel stressed today"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_level"] == "medium"
    assert body["policy_action"] == "fallback"
    assert body["fallback_reason"] == "llm_parse_failed"
    assert "If you are outside the U.S." in body["reply_text"]


def test_chat_rate_limit_applies_per_session() -> None:
    first = client.post("/api/v1/chat", json={"message": "I want to kill myself."})
    assert first.status_code == 200
    session_id = first.json()["session_id"]

    for _ in range(19):
        resp = client.post(
            "/api/v1/chat",
            json={"session_id": session_id, "message": "I want to kill myself."},
        )
        assert resp.status_code == 200

    blocked = client.post(
        "/api/v1/chat",
        json={"session_id": session_id, "message": "I want to kill myself."},
    )
    assert blocked.status_code == 429
    assert "Rate limit exceeded" in blocked.json()["detail"]


def test_chat_rate_limit_applies_per_ip_across_sessions() -> None:
    for _ in range(20):
        resp = client.post("/api/v1/chat", json={"message": "I want to kill myself."})
        assert resp.status_code == 200

    blocked = client.post("/api/v1/chat", json={"message": "I want to kill myself."})
    assert blocked.status_code == 429
    assert "Rate limit exceeded" in blocked.json()["detail"]
