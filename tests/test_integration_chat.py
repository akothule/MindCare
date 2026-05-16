"""Opt-in live API checks (Phase 4). Does not run in CI or without explicit opt-in."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from mindcare.main import app

client = TestClient(app)


def _integration_allowed() -> bool:
    if os.getenv("CI") == "true":
        return False
    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        return False
    return os.getenv("MINDCARE_RUN_INTEGRATION", "").lower() in ("1", "true", "yes")


@pytest.mark.integration
@pytest.mark.skipif(
    not _integration_allowed(),
    reason="Set MINDCARE_RUN_INTEGRATION=1 and ANTHROPIC_API_KEY; skipped on CI",
)
def test_live_chat_low_message_contract() -> None:
    resp = client.post(
        "/api/v1/chat",
        json={"message": "I feel a bit stressed about a presentation.", "metadata": {"locale": "en-US"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("session_id")
    assert body.get("reply_text")
    assert body.get("policy_action") in (
        "normal",
        "medium_llm",
        "high_template",
        "high_supporter_template",
        "high_policy_template",
        "fallback",
    )
