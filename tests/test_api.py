from fastapi.testclient import TestClient

from mindcare.config import get_settings
from mindcare.main import app
from mindcare.schemas import LLMStructuredPayload, SafetyClassificationPayload


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


def test_chat_does_not_call_safety_classifier_when_router_disabled(monkeypatch) -> None:
    def boom(*_a, **_k):
        raise AssertionError("classifier should not run when router is disabled")

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", boom)

    def fake_complete_chat_turn(
        history, latest_user_message, *, pre_medium_signals=None, soft_empathy_hints=None
    ):
        assert latest_user_message == "I feel stressed today"
        assert soft_empathy_hints is None
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


def test_classifier_high_skips_chat_llm_policy_template(monkeypatch) -> None:
    monkeypatch.setenv("MINDCARE_USE_LLM_ROUTER", "true")
    get_settings.cache_clear()

    def fake_classify(*_a, **_k):
        return SafetyClassificationPayload(
            risk_level="high",
            intent_bucket="harm_seeking",
            recommended_action="high_policy_template",
            confidence="high",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)

    def boom(*_a, **_k):
        raise AssertionError("chat LLM must not run when classifier returns high")

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", boom)

    resp = client.post("/api/v1/chat", json={"message": "edge case routed by classifier"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == "high_policy_template"
    assert body["risk_level"] == "high"
    assert "can't help" in body["reply_text"].lower()


def test_classifier_high_skips_chat_llm_crisis_template(monkeypatch) -> None:
    monkeypatch.setenv("MINDCARE_USE_LLM_ROUTER", "true")
    get_settings.cache_clear()

    def fake_classify(*_a, **_k):
        return SafetyClassificationPayload(
            risk_level="high",
            intent_bucket="crisis_ideation",
            recommended_action="high_template",
            confidence="high",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)

    def boom(*_a, **_k):
        raise AssertionError("chat LLM must not run when classifier returns high")

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", boom)

    resp = client.post("/api/v1/chat", json={"message": "another classifier-only high"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == "high_template"
    assert "really glad you shared" in body["reply_text"].lower()


def test_classifier_high_skips_chat_llm_supporter_template(monkeypatch) -> None:
    monkeypatch.setenv("MINDCARE_USE_LLM_ROUTER", "true")
    get_settings.cache_clear()

    def fake_classify(*_a, **_k):
        return SafetyClassificationPayload(
            risk_level="high",
            intent_bucket="third_party_concern",
            recommended_action="high_supporter_template",
            confidence="high",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)

    def boom(*_a, **_k):
        raise AssertionError("chat LLM must not run when classifier returns high")

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", boom)

    resp = client.post("/api/v1/chat", json={"message": "classifier-only third-party high"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == "high_supporter_template"
    assert "really glad you reached out" in body["reply_text"].lower()


def test_classifier_low_confidence_does_not_skip_chat_llm(monkeypatch) -> None:
    monkeypatch.setenv("MINDCARE_USE_LLM_ROUTER", "true")
    get_settings.cache_clear()

    def fake_classify(*_a, **_k):
        return SafetyClassificationPayload(
            risk_level="high",
            intent_bucket="x",
            recommended_action="high_template",
            confidence="low",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)

    called: list[bool] = []

    def fake_complete_chat_turn(
        _h, latest_user_message, *, pre_medium_signals=None, soft_empathy_hints=None
    ):
        called.append(True)
        assert soft_empathy_hints is None
        return LLMStructuredPayload(
            reply_text="OK",
            risk_level="low",
            suggested_policy_action="normal",
        )

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", fake_complete_chat_turn)

    resp = client.post("/api/v1/chat", json={"message": "fallback merge to regex"})
    assert resp.status_code == 200
    assert called == [True]
    assert resp.json()["policy_action"] == "normal"


def test_chat_calls_safety_classifier_when_router_enabled(monkeypatch) -> None:
    monkeypatch.setenv("MINDCARE_USE_LLM_ROUTER", "true")
    get_settings.cache_clear()

    classify_calls: list[str] = []

    def fake_classify(msg, *, history=None, pre_medium_signals=None):
        classify_calls.append(msg)
        return SafetyClassificationPayload(
            risk_level="low",
            intent_bucket="general_support",
            recommended_action="normal",
            confidence="high",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)

    def fake_complete_chat_turn(
        history, latest_user_message, *, pre_medium_signals=None, soft_empathy_hints=None
    ):
        assert soft_empathy_hints is None
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
    assert classify_calls == ["I feel stressed today"]
    body = resp.json()
    assert body["risk_level"] == "low"
    assert body["policy_action"] == "normal"


def test_router_classifier_medium_without_regex_medium_hints(monkeypatch) -> None:
    """Router on: legacy medium regex is skipped; classifier is not given pre_medium_signals."""
    monkeypatch.setenv("MINDCARE_USE_LLM_ROUTER", "true")
    get_settings.cache_clear()

    captured: list[list[str] | None] = []

    def fake_classify(_msg, *, history=None, pre_medium_signals=None):
        captured.append(list(pre_medium_signals) if pre_medium_signals else None)
        return SafetyClassificationPayload(
            risk_level="medium",
            intent_bucket="distress",
            recommended_action="medium_llm",
            confidence="high",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)

    def fake_complete_chat_turn(
        _h, latest_user_message, *, pre_medium_signals=None, soft_empathy_hints=None
    ):
        assert soft_empathy_hints is None
        assert pre_medium_signals is not None
        assert any("classifier_intent" in n for n in pre_medium_signals)
        return LLMStructuredPayload(
            reply_text="I hear you.",
            risk_level="medium",
            suggested_policy_action="medium_llm",
        )

    monkeypatch.setattr(
        "mindcare.routers.chat.complete_chat_turn",
        fake_complete_chat_turn,
    )

    resp = client.post(
        "/api/v1/chat",
        json={"message": "I don't see the point of anything anymore."},
    )
    assert resp.status_code == 200
    assert captured == [None]
    assert resp.json()["policy_action"] == "medium_llm"


def test_soft_empathy_hints_when_classifier_merges_low(monkeypatch) -> None:
    monkeypatch.setenv("MINDCARE_USE_LLM_ROUTER", "true")
    get_settings.cache_clear()

    def fake_classify(*_a, **_k):
        return SafetyClassificationPayload(
            risk_level="low",
            intent_bucket="distress",
            recommended_action="normal",
            confidence="high",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)

    captured: list[tuple[list[str] | None, list[str] | None]] = []

    def fake_complete_chat_turn(
        _h, latest_user_message, *, pre_medium_signals=None, soft_empathy_hints=None
    ):
        captured.append(
            (
                list(pre_medium_signals) if pre_medium_signals else None,
                list(soft_empathy_hints) if soft_empathy_hints else None,
            )
        )
        return LLMStructuredPayload(
            reply_text="Warm but normal-shaped reply.",
            risk_level="low",
            suggested_policy_action="normal",
        )

    monkeypatch.setattr(
        "mindcare.routers.chat.complete_chat_turn",
        fake_complete_chat_turn,
    )

    resp = client.post(
        "/api/v1/chat",
        json={"message": "I don't see the point of anything anymore."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == "normal"
    assert body["risk_level"] == "low"
    assert captured
    pre_sig, soft = captured[-1]
    assert pre_sig is None
    assert soft is not None
    assert "distress_cue" in soft


def test_soft_empathy_hints_disabled_via_env(monkeypatch) -> None:
    monkeypatch.setenv("MINDCARE_USE_LLM_ROUTER", "true")
    monkeypatch.setenv("MINDCARE_SOFT_EMPATHY_HINTS", "false")
    get_settings.cache_clear()

    def fake_classify(*_a, **_k):
        return SafetyClassificationPayload(
            risk_level="low",
            intent_bucket="general_support",
            recommended_action="normal",
            confidence="high",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)

    captured: list[list[str] | None] = []

    def fake_complete_chat_turn(
        _h, _latest_user_message, *, pre_medium_signals=None, soft_empathy_hints=None
    ):
        captured.append(
            list(soft_empathy_hints) if soft_empathy_hints else None,
        )
        return LLMStructuredPayload(
            reply_text="OK",
            risk_level="low",
            suggested_policy_action="normal",
        )

    monkeypatch.setattr(
        "mindcare.routers.chat.complete_chat_turn",
        fake_complete_chat_turn,
    )

    resp = client.post(
        "/api/v1/chat",
        json={"message": "I don't see the point of anything anymore."},
    )
    assert resp.status_code == 200
    assert captured[-1] is None


def test_chat_returns_contract_fields(monkeypatch) -> None:
    def fake_complete_chat_turn(
        history, latest_user_message, *, pre_medium_signals=None, soft_empathy_hints=None
    ):
        assert latest_user_message == "I feel stressed today"
        assert soft_empathy_hints is None
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
    def fake_complete_chat_turn(
        _history, _latest_user_message, *, pre_medium_signals=None, soft_empathy_hints=None
    ):
        assert soft_empathy_hints is None
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
