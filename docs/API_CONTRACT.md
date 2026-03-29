# MindCare API Contract Draft (MVP v0.1)

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
- `500`: internal error with safe generic fallback message
- `503`: LLM unavailable with safe retry-later message

## Behavior requirements

- If request has no `session_id`, server creates one and returns it.
- If message fails validation, do not call LLM.
- If model output parse fails, return policy-safe fallback response.
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
