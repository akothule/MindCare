# MindCare Decisions Log

Track policy and product decisions that affect implementation.

## 2026-03-22 (MVP defaults)

- **Message length limit**: 2,000 characters per user message.
- **Rate limit (MVP)**: 20 messages per 5 minutes per session and per hashed IP (see `docs/API_CONTRACT.md`).
- **Non-U.S. behavior**: Allow global access. Show U.S. resources plus generic emergency guidance with disclaimer that resources may vary by location.
- **High-risk follow-up behavior**: Keep chat enabled after a high-risk response and display a persistent crisis resources banner.
- **Location disclaimer usage**: Always include the location disclaimer line in crisis/support safety messaging.
- **Age strategy (MVP)**: Use one safety policy for all users (no age-differentiated behavior and no age-gating flow).
- **Repeated high-risk incident rule**: If a session reaches 3+ high-risk turns, keep crisis template responses and suppress normal conversational replies for the rest of that session.
- **Prompt-injection / jailbreak routing (MVP)**: Treat as high-risk safety concern; use `policy_action` `high_template` (crisis path). Reserve `blocked` for other product-specific cases if needed later.
- **LLM provider**: Claude.
- **MVP storage scope**: Remove consent and conversation storage from MVP; use ephemeral handling only. Revisit storage as a post-MVP feature.

## 2026-03-28 (docs + hosting)

- **MVP backend hosting**: [Render](https://render.com) web service for the FastAPI app (deploy after the API runs locally and the repo is connected to Git).
- **Crisis copy composition**: Clarified that high/medium template bodies (§1/§2 in `CRISIS_COPY.md`) are fixed verbatim and the location disclaimer (§5) is always appended to the same message—no conflict with “exact” wording.
- **API contract**: Renamed from “Draft” to locked MVP contract title in `API_CONTRACT.md`.
- **Test corpus**: Documented jailbreak → `high_template` for MVP; `schema_001` as harness-only for mocked parser/LLM failures.
- **Decisions captured**: Rate limit and prompt-injection routing recorded here for traceability.

## 2026-04-28 (Phase 2 readiness lock)

- **Fallback HTTP behavior**: For policy-safe fallbacks (including malformed model output), return `200` with `policy_action="fallback"` and a populated `fallback_reason`. Reserve `500/503` for infrastructure/runtime failures where a contract-shaped fallback cannot be produced.
- **Deterministic policy order**: Enforce this precedence in `/api/v1/chat`: validate/normalize input -> pre-LLM risk rules -> session state check (including 3+ high-risk lock) -> LLM generation when allowed -> post-LLM safety filter -> final policy override/template selection -> response + structured logging.
- **Template mapping**: `medium_template` and `high_template` use fixed copy from `docs/CRISIS_COPY.md`; append the location disclaimer line in the same message.
- **Observability minimum fields**: Each turn log should include `request_id`, `session_id`, final `risk_level`, final `policy_action`, `fallback_reason` (when present), and `trigger_source` (`pre_llm`, `llm`, `post_llm`, `session_lock`, `fallback`).

## 2026-04-28 (Phase 2 implementation milestone)

- **Safety layer status**: Implemented deterministic safety/fallback behavior in backend chat handler and validated with automated pytest coverage.
- **Session incident handling**: Added in-memory high-risk turn counting and 3+ high-risk session lock behavior for MVP.
- **Test posture**: Converted scaffold Phase 2 checks into active tests for medium/high template routing, fallback path, post-LLM override, and session lock.
- **Outstanding MVP gap**: Rate limiting remains pending implementation and should be completed before final MVP acceptance sign-off.

## Pending

- None.
