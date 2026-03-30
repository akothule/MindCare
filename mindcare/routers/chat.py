import logging
import time
from uuid import uuid4

import anthropic
from fastapi import APIRouter, HTTPException

from mindcare.config import get_settings
from mindcare.llm import complete_chat_turn
from mindcare.schemas import ChatRequest, ChatResponse, ResourceItem
from mindcare.session_store import get_session_store

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    settings = get_settings()
    max_len = settings.max_message_length
    started = time.perf_counter()
    msg = (req.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message must not be empty")
    if len(msg) > max_len:
        raise HTTPException(
            status_code=400,
            detail=f"message exceeds maximum length of {max_len} characters",
        )

    store = get_session_store()
    session_id = store.get_or_create_session_id(req)
    request_id = str(uuid4())

    history_before = store.history_for_prompt(session_id)

    try:
        structured = complete_chat_turn(history_before, msg)
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="LLM is not configured. Set ANTHROPIC_API_KEY in the environment.",
        ) from None
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail="The assistant could not produce a valid response. Please try again.",
        ) from None
    except anthropic.APIStatusError as e:
        logger.warning(
            "Anthropic API error: status=%s message=%s body=%s",
            e.status_code,
            e.message,
            e.body,
        )
        if e.status_code == 401:
            raise HTTPException(
                status_code=503,
                detail="Anthropic rejected the API key. Check ANTHROPIC_API_KEY in .env.",
            ) from None
        if e.status_code == 403:
            raise HTTPException(
                status_code=503,
                detail="Anthropic denied access (key permissions or account status). Check the Anthropic console.",
            ) from None
        if e.status_code == 404:
            raise HTTPException(
                status_code=503,
                detail="Model not found. Set ANTHROPIC_MODEL to a valid model id for your account (see Anthropic console / docs).",
            ) from None
        if e.status_code == 400:
            raise HTTPException(
                status_code=503,
                detail="Anthropic rejected the request (often invalid model id or quota). Check ANTHROPIC_MODEL, billing, and credits in the Anthropic console.",
            ) from None
        if e.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Anthropic rate limit. Try again shortly.",
            ) from None
        if e.status_code == 529:
            raise HTTPException(
                status_code=503,
                detail="Anthropic is temporarily overloaded. Try again shortly.",
            ) from None
        raise HTTPException(
            status_code=503,
            detail=f"Anthropic returned an error ({e.status_code}). See server logs for details.",
        ) from None
    except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
        logger.warning("Anthropic network error: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Could not reach Anthropic. Check your network connection.",
        ) from None
    except Exception:
        logger.exception("Unexpected error in /chat")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong. Please try again in a moment.",
        ) from None

    reply = structured.reply_text.strip() or settings.empty_reply_fallback
    store.append_user_message(session_id, msg)
    store.append_assistant_message(session_id, reply)

    resources: list[ResourceItem] = []
    # Skeleton: populate resources for medium/high in Phase 2 using CRISIS_COPY.md

    latency_ms = int((time.perf_counter() - started) * 1000)

    return ChatResponse(
        session_id=session_id,
        request_id=request_id,
        reply_text=reply,
        risk_level=structured.risk_level,
        policy_action=structured.suggested_policy_action,
        resources=resources,
        fallback_reason=None,
        latency_ms=latency_ms,
    )
