# MindCare API Contract (MVP v0.1)

This contract is designed to support deterministic safety behavior and robust fallbacks.

## Endpoint

- `POST /api/v1/chat`

## Request JSON

```json
{
  "session_id": "optional-uuid",
  "message": "string, required",
  "metadata": {
    "locale": "en-US",
    "user_agent": "optional string",
    "client_timestamp": "optional ISO-8601"
  }
}
```

## Response JSON

```json
{
  "session_id": "uuid",
  "request_id": "uuid",
  "reply_text": "string",
  "risk_level": "low | medium | high",
  "policy_action": "normal | medium_template | high_template | fallback | blocked",
  "resources": [
    {
      "label": "988 Suicide & Crisis Lifeline",
      "value": "Call or text 988"
    }
  ],
  "fallback_reason": "nullable string",
  "latency_ms": 0
}
```

## Error responses

- `400`: invalid request (empty message, too long, bad schema)
- `429`: rate-limited
- `500`: internal error when a contract-shaped fallback cannot be produced
- `503`: upstream provider unavailable/network failure where fallback cannot be produced

## Behavior requirements

- If request has no `session_id`, server creates one and returns it.
- If message fails validation, do not call LLM.
- If model output parse/schema validation fails, return `200` with a policy-safe fallback response and `policy_action="fallback"`.
- If post-LLM safety filter catches disallowed content, return a policy-safe response with final `policy_action` set by policy override.
- `risk_level` in response is final risk level after policy overrides.
- `policy_action` must always be present for observability.

## Suggested limits (initial)

- `message` max length: 2,000 chars
- Context window retained per session: last 8 to 10 turns
- Rate limit: 20 messages per 5 minutes per session and per hashed IP

## Finalized MVP defaults

- Geo behavior: allow global use, but include generic emergency guidance plus U.S. resources with a location disclaimer.
- High-risk follow-up UX behavior: continue chat and show a persistent crisis resources banner.
- Always include location disclaimer text in crisis/support safety messaging.
- Age behavior: single safety policy for all users in MVP (no age differentiation).
- Incident rule: after 3+ high-risk turns in a session, pin crisis UI and suppress normal conversational responses.

## Post-MVP items (deferred)

- Consent-based storage preferences.
- Conversation persistence and retention policy.
