import json
import re
from typing import Optional, Sequence

import anthropic

from pydantic import ValidationError

from mindcare.config import get_settings
from mindcare.prompts import load_system_prompt
from mindcare.schemas import LLMStructuredPayload


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


def complete_chat_turn(
    history: list[dict[str, str]],
    latest_user_message: str,
    *,
    pre_medium_signals: Sequence[str] | None = None,
) -> LLMStructuredPayload:
    """Call Claude with conversation context; parse structured JSON.

    Optional ``pre_medium_signals`` are heuristic matches (never shown to the end user)
    appended to the final user turn so the model can calibrate empathy and ``risk_level``.
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
    tail = latest_user_message
    if pre_medium_signals:
        notes = "; ".join(str(s) for s in pre_medium_signals)
        tail = f"{latest_user_message}{_MEDIUM_SIGNAL_PREFIX}{notes}]"
    messages.append({"role": "user", "content": tail})

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
