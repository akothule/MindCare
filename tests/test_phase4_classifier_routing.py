"""Phase 4: mocked classifier + merge outcomes (requires MINDCARE_USE_LLM_ROUTER in test)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mindcare.config import get_settings
from mindcare.main import app
from mindcare.schemas import LLMStructuredPayload, SafetyClassificationPayload

client = TestClient(app)

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "docs" / "TEST_PROMPT_CORPUS.json"
_CLASSIFIER_FOCUS_IDS = frozenset(
    {
        "class_low_third_party_001",
        "class_low_educational_001",
        "class_low_friend_language_001",
        "class_medium_negation_001",
        "class_medium_meta_001",
        "class_high_third_party_report_001",
    }
)


def _payload(message: str) -> dict:
    return {"message": message, "metadata": {"locale": "en-US"}}


def _case_by_id(case_id: str) -> dict:
    data = json.loads(_CORPUS_PATH.read_text())
    for c in data["cases"]:
        if c["id"] == case_id:
            return c
    raise KeyError(case_id)


@pytest.fixture
def router_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDCARE_USE_LLM_ROUTER", "true")
    get_settings.cache_clear()


def test_corpus_classifier_focus_cases_baseline_router_off_matches_corpus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity: new v0.2 cases still match JSON expectations with router off (conftest default)."""

    def _fake_ok(_h, msg: str, *, pre_medium_signals=None, soft_empathy_hints=None):
        return LLMStructuredPayload(
            reply_text="stub",
            risk_level="medium" if pre_medium_signals else "low",
            suggested_policy_action="medium_llm" if pre_medium_signals else "normal",
        )

    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", _fake_ok)

    for cid in _CLASSIFIER_FOCUS_IDS:
        case = _case_by_id(cid)
        resp = client.post("/api/v1/chat", json=_payload(case["input"]))
        assert resp.status_code == 200, cid
        body = resp.json()
        assert body["policy_action"] == case["expected_policy_action"], cid


def test_router_trusted_low_with_regex_medium_soft_empathy_normal(router_on, monkeypatch: pytest.MonkeyPatch) -> None:
    """Router on skips regex medium; soft empathy uses classifier intent_bucket (one Haiku)."""
    msg = _case_by_id("class_medium_negation_001")["input"]

    def fake_classify(*_a, **_k):
        return SafetyClassificationPayload(
            risk_level="low",
            intent_bucket="distress",
            recommended_action="normal",
            confidence="high",
        )

    captured: list[list[str] | None] = []

    def fake_complete(_h, _m, *, pre_medium_signals=None, soft_empathy_hints=None):
        captured.append(list(soft_empathy_hints) if soft_empathy_hints else None)
        return LLMStructuredPayload(
            reply_text="OK",
            risk_level="low",
            suggested_policy_action="normal",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)
    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", fake_complete)

    resp = client.post("/api/v1/chat", json=_payload(msg))
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == "normal"
    assert body["risk_level"] == "low"
    assert captured and captured[-1] is not None


def test_router_trusted_medium_keeps_medium_llm(router_on, monkeypatch: pytest.MonkeyPatch) -> None:
    msg = _case_by_id("class_medium_negation_001")["input"]

    def fake_classify(*_a, **_k):
        return SafetyClassificationPayload(
            risk_level="medium",
            intent_bucket="distress",
            recommended_action="medium_llm",
            confidence="high",
        )

    def fake_complete(_h, _m, *, pre_medium_signals=None, soft_empathy_hints=None):
        assert soft_empathy_hints is None
        assert pre_medium_signals is not None
        return LLMStructuredPayload(
            reply_text="Heard.",
            risk_level="medium",
            suggested_policy_action="medium_llm",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)
    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", fake_complete)

    resp = client.post("/api/v1/chat", json=_payload(msg))
    assert resp.status_code == 200
    assert resp.json()["policy_action"] == "medium_llm"


def test_router_untrusted_classifier_soft_fallback_then_chat_medium(router_on, monkeypatch: pytest.MonkeyPatch) -> None:
    """Untrusted classifier: merge follows pre_risk (low when regex medium skipped); chat JSON can still elevate."""
    msg = _case_by_id("class_medium_negation_001")["input"]

    def fake_classify(*_a, **_k):
        return SafetyClassificationPayload(
            risk_level="low",
            intent_bucket="x",
            recommended_action="normal",
            confidence="low",
        )

    def fake_complete(_h, _m, *, pre_medium_signals=None, soft_empathy_hints=None):
        assert soft_empathy_hints is None
        return LLMStructuredPayload(
            reply_text="OK",
            risk_level="medium",
            suggested_policy_action="medium_llm",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)
    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", fake_complete)

    resp = client.post("/api/v1/chat", json=_payload(msg))
    assert resp.status_code == 200
    assert resp.json()["policy_action"] == "medium_llm"


def test_router_on_classifier_medium_without_regex_phrases(router_on, monkeypatch: pytest.MonkeyPatch) -> None:
    """No legacy medium_keyword match; trusted classifier returns medium → medium_llm + signals."""
    msg = "Everything feels heavy and I am exhausted but I am safe right now."

    def fake_classify(*_a, **_k):
        return SafetyClassificationPayload(
            risk_level="medium",
            intent_bucket="distress",
            recommended_action="medium_llm",
            confidence="high",
        )

    captured: list[list[str] | None] = []

    def fake_complete(_h, _m, *, pre_medium_signals=None, soft_empathy_hints=None):
        captured.append(list(pre_medium_signals) if pre_medium_signals else None)
        assert soft_empathy_hints is None
        return LLMStructuredPayload(
            reply_text="Heard you.",
            risk_level="medium",
            suggested_policy_action="medium_llm",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)
    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", fake_complete)

    resp = client.post("/api/v1/chat", json=_payload(msg))
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == "medium_llm"
    assert body["risk_level"] == "medium"
    assert captured and captured[-1] is not None
    assert any("classifier_intent" in x for x in captured[-1])


def test_router_third_party_low_stays_normal_when_classifier_low(router_on, monkeypatch: pytest.MonkeyPatch) -> None:
    msg = _case_by_id("class_low_third_party_001")["input"]

    def fake_classify(*_a, **_k):
        return SafetyClassificationPayload(
            risk_level="low",
            intent_bucket="third_party_concern",
            recommended_action="normal",
            confidence="high",
        )

    def fake_complete(_h, _m, *, pre_medium_signals=None, soft_empathy_hints=None):
        assert soft_empathy_hints is None
        assert pre_medium_signals is None
        return LLMStructuredPayload(
            reply_text="Supportive.",
            risk_level="low",
            suggested_policy_action="normal",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)
    monkeypatch.setattr("mindcare.routers.chat.complete_chat_turn", fake_complete)

    resp = client.post("/api/v1/chat", json=_payload(msg))
    assert resp.status_code == 200
    body = resp.json()
    assert body["policy_action"] == "normal"
    assert body["risk_level"] == "low"
