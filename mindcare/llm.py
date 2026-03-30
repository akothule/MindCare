import json
import re
from typing import Optional

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


def complete_chat_turn(history: list[dict[str, str]], latest_user_message: str) -> LLMStructuredPayload:
    """Call Claude with conversation context; parse structured JSON."""
    settings = get_settings()
    if not settings.anthropic_api_key.strip():
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    messages: list[dict] = []
    for turn in history:
        if turn["role"] in ("user", "assistant"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    # Always send the current user message as the final turn (history is prior turns only).
    messages.append({"role": "user", "content": latest_user_message})

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
