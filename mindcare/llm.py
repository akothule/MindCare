import json
import re
from typing import Optional, Sequence

import anthropic

from pydantic import ValidationError

from mindcare.config import get_settings
from mindcare.prompts import load_classifier_system_prompt, load_system_prompt
from mindcare.schemas import LLMStructuredPayload, SafetyClassificationPayload


def _extract_json(text: str) -> Optional[dict]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            return None
    return None


_MEDIUM_SIGNAL_PREFIX = (
    "\n\n[Internal note for MindCare routing only — "
    "do not repeat verbatim; automated screening suggests possible distress: "
)

_SOFT_EMPATHY_PREFIX = (
    "\n\n[Internal calibration — safety routing for this turn is LOW. "
    "The user text matched optional distress heuristics; use brief validation and warmth. "
    "Do NOT add crisis hotline lists, structured 988 resource blocks, or long safety footers "
    "unless the user clearly escalates or implies imminent risk. Do not quote this note. Cues: "
)


def apply_internal_routing_notes(
    latest_user_message: str,
    notes: Sequence[str] | None,
) -> str:
    """Append heuristic routing hints to the user text (classifier or chat LLM)."""
    text = latest_user_message.strip()
    if not notes:
        return text
    joined = "; ".join(str(s) for s in notes)
    return f"{text}{_MEDIUM_SIGNAL_PREFIX}{joined}]"


def apply_soft_empathy_calibration(
    latest_user_message: str,
    cues: Sequence[str] | None,
) -> str:
    """Lightweight chat-only hints when merge is low but regex distress heuristics fired."""
    text = latest_user_message.strip()
    if not cues:
        return text
    joined = "; ".join(str(c) for c in cues)
    return f"{text}{_SOFT_EMPATHY_PREFIX}{joined}]"


def complete_chat_turn(
    history: list[dict[str, str]],
    latest_user_message: str,
    *,
    pre_medium_signals: Sequence[str] | None = None,
    soft_empathy_hints: Sequence[str] | None = None,
) -> LLMStructuredPayload:
    """Call Claude with conversation context; parse structured JSON.

    Optional ``pre_medium_signals`` are heuristic matches (never shown to the end user)
    appended to the final user turn so the model can calibrate empathy and ``risk_level``.

    Optional ``soft_empathy_hints`` (short categorical cues) apply when routing is low but
    distress heuristics matched — tighter instructions than ``pre_medium_signals`` so the
    reply stays in the low-risk shape without crisis resource blocks.
    """
    settings = get_settings()
    if not settings.anthropic_api_key.strip():
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    messages: list[dict] = []
    for turn in history:
        if turn["role"] in ("user", "assistant"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    # Always send the current user message as the final turn (history is prior turns only).
    if pre_medium_signals:
        user_content = apply_internal_routing_notes(latest_user_message, pre_medium_signals)
    elif soft_empathy_hints:
        user_content = apply_soft_empathy_calibration(latest_user_message, soft_empathy_hints)
    else:
        user_content = latest_user_message.strip()
    messages.append({"role": "user", "content": user_content})

    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
        system=load_system_prompt(),
        messages=messages,
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text

    parsed = _extract_json(text)
    if not parsed:
        raise ValueError("Model did not return parseable JSON")

    try:
        return LLMStructuredPayload.model_validate(parsed)
    except ValidationError as e:
        raise ValueError("Model JSON did not match expected schema") from e


def classify_safety_turn(
    latest_user_message: str,
    *,
    history: Sequence[dict[str, str]] | None = None,
    pre_medium_signals: Sequence[str] | None = None,
) -> SafetyClassificationPayload:
    """Dedicated classifier completion: validated JSON only.

    ``history`` is reserved for future context (e.g. last *k* turns); Phase 1 uses the
    latest user message only to match the plan's message-only default.

    ``pre_medium_signals`` (Phase 3): legacy medium-regex hits as hints only when the
    LLM router is on — they do not alone set ``pre_risk`` for trusted merge.
    """
    _ = history

    settings = get_settings()
    if not settings.anthropic_api_key.strip():
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    model = (settings.mindcare_classifier_model or "").strip() or settings.anthropic_model
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    response = client.messages.create(
        model=model,
        max_tokens=settings.mindcare_classifier_max_tokens,
        system=load_classifier_system_prompt(),
        messages=[
            {
                "role": "user",
                "content": apply_internal_routing_notes(latest_user_message, pre_medium_signals),
            }
        ],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text

    parsed = _extract_json(text)
    if not parsed:
        raise ValueError("Classifier did not return parseable JSON")

    try:
        return SafetyClassificationPayload.model_validate(parsed)
    except ValidationError as e:
        raise ValueError("Classifier JSON did not match expected schema") from e
