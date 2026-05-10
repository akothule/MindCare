"""Pre-chat risk merge: regex + optional LLM classifier (see docs/SAFETY_POLICY.md §4).

When the chat handler skips legacy medium regex (LLM router on), ``pre_risk`` is usually
``low`` and medium vs low comes only from the classifier. Merge still uses
``baseline = low if pre_risk == medium else pre_risk`` then ``max(baseline, clf.risk)``.

Router off: ``pre_risk`` includes regex medium; ``merged_risk`` follows regex when the
classifier is absent or untrusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mindcare.schemas import SafetyClassificationPayload

RiskLevel = Literal["low", "medium", "high"]
HighTemplateKind = Literal["crisis", "policy", "supporter"]

_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


def max_risk(a: str, b: str) -> str:
    return a if _RANK[a] >= _RANK[b] else b


@dataclass(frozen=True)
class PreChatMergeResult:
    """Single source of truth for pre-chat merge before the conversational LLM."""

    merged_risk: RiskLevel
    classifier_trusted: bool
    classifier_soft_fallback: bool
    high_template_kind: HighTemplateKind | None
    medium_signal_notes: tuple[str, ...]


def _medium_signal_notes(
    merged_risk: str,
    pre_risk: str,
    pre_keyword_notes: list[str],
    classifier_trusted: bool,
    classification: SafetyClassificationPayload | None,
) -> tuple[str, ...]:
    if merged_risk != "medium":
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for n in pre_keyword_notes:
        if n not in seen:
            seen.add(n)
            out.append(n)
    if classifier_trusted and classification is not None and classification.risk_level == "medium":
        tag = f"classifier_intent:{classification.intent_bucket}"
        if tag not in seen:
            out.append(tag)
    return tuple(out)


def _high_kind_from_classifier(
    classification: SafetyClassificationPayload,
) -> HighTemplateKind:
    if classification.recommended_action == "high_policy_template":
        return "policy"
    if classification.recommended_action == "high_supporter_template":
        return "supporter"
    return "crisis"


def merge_pre_chat_risk(
    *,
    router_enabled: bool,
    pre_risk: str,
    pre_keyword_notes: list[str],
    classification: SafetyClassificationPayload | None,
) -> PreChatMergeResult:
    """Compute ``merged_pre_chat`` for the LLM-eligible path (past hard gates and session lock).

    - Router off: ``merged_risk == pre_risk`` (legacy regex only).
    - Router on, classifier missing or ``confidence == \"low\"``: soft fallback — regex only
      (same as ``pre_risk`` for this path; hard gates unchanged).
    - Router on, ``confidence`` in (``high``, ``medium``): **Phase 3** — with regex medium
      disabled in the handler, ``pre_risk`` is usually ``low``; then
      ``merged_risk = max(pre_risk, classification.risk_level)`` (same formula as
      ``max(low, clf)`` for non-high ``pre_risk``). If router off, ``pre_risk`` can be
      regex-medium and ``baseline`` is ``low`` only for that case so a trusted classifier
      can still return **low** without being overridden by regex medium alone.

    When ``merged_risk == \"high\"`` on this path, high risk always comes from a **trusted**
    classifier (regex already returned early for high). Template kind follows
    ``recommended_action``: ``high_policy_template`` → policy, ``high_supporter_template`` →
    supporter (third-party copy), else crisis (first-person template).
    """
    if not router_enabled:
        return PreChatMergeResult(
            merged_risk=pre_risk,  # type: ignore[arg-type]
            classifier_trusted=False,
            classifier_soft_fallback=False,
            high_template_kind=None,
            medium_signal_notes=_medium_signal_notes(
                pre_risk, pre_risk, pre_keyword_notes, False, None
            ),
        )

    trusted = (
        classification is not None and classification.confidence in ("high", "medium")
    )
    soft_fallback = not trusted

    if soft_fallback:
        merged = pre_risk
    else:
        assert classification is not None
        baseline = "low" if pre_risk == "medium" else pre_risk
        merged = max_risk(baseline, classification.risk_level)

    high_kind: HighTemplateKind | None = None
    if merged == "high":
        assert classification is not None and trusted
        high_kind = _high_kind_from_classifier(classification)

    notes = _medium_signal_notes(
        merged, pre_risk, pre_keyword_notes, trusted, classification
    )

    return PreChatMergeResult(
        merged_risk=merged,  # type: ignore[arg-type]
        classifier_trusted=trusted,
        classifier_soft_fallback=soft_fallback,
        high_template_kind=high_kind,
        medium_signal_notes=notes,
    )
