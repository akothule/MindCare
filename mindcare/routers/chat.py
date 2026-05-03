import logging
import re
import time
from uuid import uuid4

import anthropic
from fastapi import APIRouter, HTTPException, Request

from mindcare.config import get_settings
from mindcare.llm import complete_chat_turn
from mindcare.rate_limiter import get_chat_rate_limiter
from mindcare.schemas import ChatRequest, ChatResponse, ResourceItem
from mindcare.session_store import get_session_store

logger = logging.getLogger(__name__)

router = APIRouter()

_LOCATION_DISCLAIMER = (
    "If you are outside the U.S., local emergency and crisis services may be different. "
    "If you are in immediate danger, please contact your local emergency number now."
)

_HIGH_TEMPLATE_BODY = (
    "I'm really glad you shared this. I am concerned about your immediate safety.\n\n"
    "You deserve support right now from people who can help in real time:\n"
    "- Call or text **988** (Suicide & Crisis Lifeline, U.S.) any time, 24/7.\n"
    "- If you may act on these thoughts now, call **911** right away.\n"
    "- If possible, move to a safer place and contact a trusted person who can stay with you.\n\n"
    "I am not an emergency service, but your safety matters and reaching out now can help keep you safe."
)

_MEDIUM_TEMPLATE_BODY = (
    "Thank you for being honest about how hard this feels. You don't have to carry this alone.\n\n"
    "It may help to reach out to someone you trust today and connect with professional support:\n"
    "- Call or text **988** for immediate emotional support.\n"
    "- Crisis Text Line: text **HOME** to **741741**.\n"
    "- NAMI HelpLine: **1-800-950-6264**.\n\n"
    "If you feel in immediate danger, call **911**."
)

_RESOURCE_ITEMS = [
    ResourceItem(label="988 Suicide & Crisis Lifeline", value="Call or text 988"),
    ResourceItem(label="Crisis Text Line", value="Text HOME to 741741"),
    ResourceItem(label="NAMI HelpLine", value="1-800-950-6264"),
    ResourceItem(label="Emergency", value="Call 911 if in immediate danger"),
]

_HIGH_PATTERNS = [
    r"\bkill myself\b",
    r"\bend my life\b",
    r"\bsuicide\b",
    r"\bhurt myself\b",
    r"\boverdose\b",
    r"\bplan to hurt myself\b",
    r"\bwant to die\b",
]

_MEDIUM_PATTERNS = [
    r"\bdon't see the point\b",
    r"\bno point of anything\b",
    r"\bwish i could disappear\b",
    r"\bbetter off without me\b",
    r"\bfeel hopeless\b",
    r"\bcan't keep going\b",
]

_INJECTION_PATTERNS = [
    r"\bignore (all|previous|prior) (rules|instructions)\b",
    r"\bjailbreak\b",
    r"\bself-harm instructions\b",
]

_DISALLOWED_REPLY_PATTERNS = [
    r"\bhow to (kill yourself|hurt yourself|overdose)\b",
    r"\bdosage\b",
    r"\bmg\b",
    r"\bstep-by-step\b",
]

_RISK_RANK = {"low": 0, "medium": 1, "high": 2}


def _with_disclaimer(template_body: str) -> str:
    return f"{template_body}\n\n{_LOCATION_DISCLAIMER}"


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def _pre_llm_risk(message: str) -> str:
    if _matches_any(message, _HIGH_PATTERNS) or _matches_any(message, _INJECTION_PATTERNS):
        return "high"
    if _matches_any(message, _MEDIUM_PATTERNS):
        return "medium"
    return "low"


def _is_disallowed_output(text: str) -> bool:
    return _matches_any(text, _DISALLOWED_REPLY_PATTERNS)


def _max_risk(a: str, b: str) -> str:
    return a if _RISK_RANK[a] >= _RISK_RANK[b] else b


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request) -> ChatResponse:
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
    limiter = get_chat_rate_limiter(
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    client_ip = request.client.host if request.client and request.client.host else "unknown"
    if not limiter.allow(session_id=session_id, client_ip=client_ip):
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded. Maximum {settings.rate_limit_max_requests} "
                f"requests per {settings.rate_limit_window_seconds} seconds."
            ),
        )
    request_id = str(uuid4())
    pre_risk = _pre_llm_risk(msg)
    high_risk_count = store.high_risk_count(session_id)

    history_before = store.history_for_prompt(session_id)

    def _template_response(
        *,
        template: str,
        risk_level: str,
        policy_action: str,
        fallback_reason: str | None,
        trigger_source: str,
    ) -> ChatResponse:
        if risk_level == "high":
            store.increment_high_risk(session_id)
        store.append_user_message(session_id, msg)
        store.append_assistant_message(session_id, template)
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "chat_policy_template request_id=%s session_id=%s risk_level=%s policy_action=%s fallback_reason=%s trigger_source=%s latency_ms=%s",
            request_id,
            session_id,
            risk_level,
            policy_action,
            fallback_reason,
            trigger_source,
            latency_ms,
        )
        return ChatResponse(
            session_id=session_id,
            request_id=request_id,
            reply_text=template,
            risk_level=risk_level,
            policy_action=policy_action,
            resources=list(_RESOURCE_ITEMS),
            fallback_reason=fallback_reason,
            latency_ms=latency_ms,
        )

    if high_risk_count >= 3:
        return _template_response(
            template=_with_disclaimer(_HIGH_TEMPLATE_BODY),
            risk_level="high",
            policy_action="high_template",
            fallback_reason=None,
            trigger_source="session_lock",
        )

    if pre_risk == "high":
        return _template_response(
            template=_with_disclaimer(_HIGH_TEMPLATE_BODY),
            risk_level="high",
            policy_action="high_template",
            fallback_reason=None,
            trigger_source="pre_llm",
        )

    if pre_risk == "medium":
        return _template_response(
            template=_with_disclaimer(_MEDIUM_TEMPLATE_BODY),
            risk_level="medium",
            policy_action="medium_template",
            fallback_reason=None,
            trigger_source="pre_llm",
        )

    try:
        structured = complete_chat_turn(history_before, msg)
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="LLM is not configured. Set ANTHROPIC_API_KEY in the environment.",
        ) from None
    except ValueError:
        return _template_response(
            template=_with_disclaimer(_MEDIUM_TEMPLATE_BODY),
            risk_level="medium",
            policy_action="fallback",
            fallback_reason="llm_parse_failed",
            trigger_source="fallback",
        )
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
    final_risk = _max_risk(pre_risk, structured.risk_level)

    if _is_disallowed_output(reply):
        return _template_response(
            template=_with_disclaimer(_HIGH_TEMPLATE_BODY),
            risk_level="high",
            policy_action="high_template",
            fallback_reason="post_llm_disallowed_output",
            trigger_source="post_llm",
        )

    if final_risk == "high":
        return _template_response(
            template=_with_disclaimer(_HIGH_TEMPLATE_BODY),
            risk_level="high",
            policy_action="high_template",
            fallback_reason=None,
            trigger_source="llm",
        )

    if final_risk == "medium":
        return _template_response(
            template=_with_disclaimer(_MEDIUM_TEMPLATE_BODY),
            risk_level="medium",
            policy_action="medium_template",
            fallback_reason=None,
            trigger_source="llm",
        )

    store.append_user_message(session_id, msg)
    store.append_assistant_message(session_id, reply)
    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "chat_policy_normal request_id=%s session_id=%s risk_level=%s policy_action=normal fallback_reason=None trigger_source=llm latency_ms=%s",
        request_id,
        session_id,
        final_risk,
        latency_ms,
    )
    return ChatResponse(
        session_id=session_id,
        request_id=request_id,
        reply_text=reply,
        risk_level="low",
        policy_action="normal",
        resources=[],
        fallback_reason=None,
        latency_ms=latency_ms,
    )
