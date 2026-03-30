from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high"]
PolicyAction = Literal["normal", "medium_template", "high_template", "fallback", "blocked"]


class ChatMetadata(BaseModel):
    locale: Optional[str] = "en-US"
    user_agent: Optional[str] = None
    client_timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    metadata: Optional[ChatMetadata] = None


class ResourceItem(BaseModel):
    label: str
    value: str


class ChatResponse(BaseModel):
    session_id: str
    request_id: str
    reply_text: str
    risk_level: RiskLevel
    policy_action: PolicyAction
    resources: list[ResourceItem] = Field(default_factory=list)
    fallback_reason: Optional[str] = None
    latency_ms: int = 0


class LLMStructuredPayload(BaseModel):
    """Expected JSON shape from the model (skeleton; tighten in Phase 2+)."""

    reply_text: str
    risk_level: RiskLevel = "low"
    suggested_policy_action: PolicyAction = "normal"
