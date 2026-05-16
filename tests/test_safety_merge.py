"""Unit tests for pre-chat merge (Phase 2 router)."""

from mindcare.safety_merge import merge_pre_chat_risk, max_risk
from mindcare.schemas import SafetyClassificationPayload


def test_max_risk_ordering() -> None:
    assert max_risk("low", "medium") == "medium"
    assert max_risk("medium", "low") == "medium"
    assert max_risk("high", "medium") == "high"


def test_router_off_matches_regex_only() -> None:
    r = merge_pre_chat_risk(
        router_enabled=False,
        pre_risk="medium",
        pre_keyword_notes=["medium_keyword: x"],
        classification=None,
    )
    assert r.merged_risk == "medium"
    assert not r.classifier_trusted
    assert not r.classifier_soft_fallback
    assert r.high_template_kind is None
    assert "medium_keyword: x" in r.medium_signal_notes


def test_soft_fallback_ignores_classifier_risk() -> None:
    clf = SafetyClassificationPayload(
        risk_level="high",
        intent_bucket="crisis",
        recommended_action="high_template",
        confidence="low",
    )
    r = merge_pre_chat_risk(
        router_enabled=True,
        pre_risk="low",
        pre_keyword_notes=[],
        classification=clf,
    )
    assert r.merged_risk == "low"
    assert r.classifier_soft_fallback
    assert not r.classifier_trusted
    assert r.high_template_kind is None


def test_trusted_classifier_escalates_to_high_policy() -> None:
    clf = SafetyClassificationPayload(
        risk_level="high",
        intent_bucket="harm_seeking",
        recommended_action="high_policy_template",
        confidence="high",
    )
    r = merge_pre_chat_risk(
        router_enabled=True,
        pre_risk="low",
        pre_keyword_notes=[],
        classification=clf,
    )
    assert r.merged_risk == "high"
    assert r.classifier_trusted
    assert not r.classifier_soft_fallback
    assert r.high_template_kind == "policy"


def test_trusted_classifier_escalates_to_high_crisis() -> None:
    clf = SafetyClassificationPayload(
        risk_level="high",
        intent_bucket="crisis_ideation",
        recommended_action="high_template",
        confidence="medium",
    )
    r = merge_pre_chat_risk(
        router_enabled=True,
        pre_risk="low",
        pre_keyword_notes=[],
        classification=clf,
    )
    assert r.merged_risk == "high"
    assert r.high_template_kind == "crisis"


def test_trusted_classifier_escalates_to_high_supporter() -> None:
    clf = SafetyClassificationPayload(
        risk_level="high",
        intent_bucket="third_party_concern",
        recommended_action="high_supporter_template",
        confidence="high",
    )
    r = merge_pre_chat_risk(
        router_enabled=True,
        pre_risk="low",
        pre_keyword_notes=[],
        classification=clf,
    )
    assert r.merged_risk == "high"
    assert r.high_template_kind == "supporter"


def test_phase3_trusted_classifier_low_overrides_regex_medium_signals() -> None:
    """Phase 3: regex medium is hints only; trusted classifier can merge to low."""
    clf = SafetyClassificationPayload(
        risk_level="low",
        intent_bucket="general_support",
        recommended_action="normal",
        confidence="high",
    )
    r = merge_pre_chat_risk(
        router_enabled=True,
        pre_risk="medium",
        pre_keyword_notes=["medium_keyword: y"],
        classification=clf,
    )
    assert r.merged_risk == "low"
    assert r.medium_signal_notes == ()


def test_soft_fallback_preserves_regex_medium_when_classifier_untrusted() -> None:
    clf = SafetyClassificationPayload(
        risk_level="low",
        intent_bucket="general_support",
        recommended_action="normal",
        confidence="low",
    )
    r = merge_pre_chat_risk(
        router_enabled=True,
        pre_risk="medium",
        pre_keyword_notes=["medium_keyword: z"],
        classification=clf,
    )
    assert r.merged_risk == "medium"
    assert "medium_keyword: z" in r.medium_signal_notes


def test_phase3_trusted_medium_with_regex_hints_keeps_merged_medium() -> None:
    clf = SafetyClassificationPayload(
        risk_level="medium",
        intent_bucket="distress",
        recommended_action="medium_llm",
        confidence="high",
    )
    r = merge_pre_chat_risk(
        router_enabled=True,
        pre_risk="medium",
        pre_keyword_notes=["medium_keyword: pat"],
        classification=clf,
    )
    assert r.merged_risk == "medium"
    assert "medium_keyword: pat" in r.medium_signal_notes
    assert "classifier_intent:distress" in r.medium_signal_notes


def test_classifier_medium_adds_intent_note_when_regex_low() -> None:
    clf = SafetyClassificationPayload(
        risk_level="medium",
        intent_bucket="third_party_concern",
        recommended_action="medium_llm",
        confidence="high",
    )
    r = merge_pre_chat_risk(
        router_enabled=True,
        pre_risk="low",
        pre_keyword_notes=[],
        classification=clf,
    )
    assert r.merged_risk == "medium"
    assert "classifier_intent:third_party_concern" in r.medium_signal_notes
