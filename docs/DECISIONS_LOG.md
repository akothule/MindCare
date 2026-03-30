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

## Pending

- None.
