from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

RiskLevel = Literal["low", "medium", "high"]
ClassifierConfidence = Literal["high", "medium", "low"]
PolicyAction = Literal[
    "normal",
    "medium_llm",
    "medium_template",
    "high_template",
    "high_supporter_template",
    "high_policy_template",
    "fallback",
    "blocked",
]


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
    """Expected JSON shape from the model response."""

    reply_text: str
    risk_level: RiskLevel = "low"
    suggested_policy_action: PolicyAction = "normal"


class SafetyClassificationPayload(BaseModel):
    """Structured JSON from the dedicated safety classifier (routing only)."""

    risk_level: RiskLevel = "low"
    intent_bucket: str = Field(default="general_support", max_length=128)
    recommended_action: PolicyAction = "normal"
    confidence: ClassifierConfidence = "low"
    rationale: Optional[str] = Field(default=None, max_length=500)

    @field_validator("intent_bucket")
    @classmethod
    def intent_bucket_non_empty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            return "general_support"
        return s
