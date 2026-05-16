import re

import pytest

from mindcare.config import get_settings
from mindcare.schemas import SafetyClassificationPayload
from mindcare.rate_limiter import get_chat_rate_limiter
from mindcare.session_store import get_session_store


@pytest.fixture(autouse=True)
def reset_in_memory_runtime_state(monkeypatch: pytest.MonkeyPatch) -> None:
    # Isolate tests from repo-root .env (e.g. MINDCARE_USE_LLM_ROUTER=true).
    monkeypatch.setenv("MINDCARE_USE_LLM_ROUTER", "false")
    # So pre-LLM crisis_perspective runs the stubbed classifier without a real key.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "pytest-stub-key")
    get_settings.cache_clear()
    store = get_session_store()
    store._sessions.clear()  # noqa: SLF001
    store._high_risk_counts.clear()  # noqa: SLF001

    settings = get_settings()
    limiter = get_chat_rate_limiter(
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    limiter.reset()


@pytest.fixture(autouse=True)
def stub_safety_classifier_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline stand-in for ``classify_safety_turn`` (patch the name bound in ``chat`` router)."""

    def fake_classify(latest_user_message: str) -> SafetyClassificationPayload:
        m = (latest_user_message or "").lower()
        if re.search(r"\b(kill myself|hurt myself|plan to hurt myself|end my life)\b", m):
            return SafetyClassificationPayload(
                risk_level="high",
                intent_bucket="crisis_ideation",
                recommended_action="high_template",
                confidence="high",
            )
        if re.search(
            r"\b(my friend|our friend|he said|she said|worried about him|worried about her)\b",
            m,
        ) and re.search(r"\b(suicide|suicidal|overdose|kill herself|kill himself)\b", m):
            return SafetyClassificationPayload(
                risk_level="high",
                intent_bucket="third_party_concern",
                recommended_action="high_supporter_template",
                confidence="high",
            )
        return SafetyClassificationPayload(
            risk_level="low",
            intent_bucket="general_support",
            recommended_action="normal",
            confidence="high",
        )

    monkeypatch.setattr("mindcare.routers.chat.classify_safety_turn", fake_classify)
