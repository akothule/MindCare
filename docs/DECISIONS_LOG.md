# MindCare Decisions Log

Track policy and product decisions that affect implementation.

## 2026-03-22 (MVP defaults)

- **Message length limit**: 2,000 characters per user message.
- **Non-U.S. behavior**: Allow global access. Show U.S. resources plus generic emergency guidance with disclaimer that resources may vary by location.
- **High-risk follow-up behavior**: Keep chat enabled after a high-risk response and display a persistent crisis resources banner.
- **Location disclaimer usage**: Always include the location disclaimer line in crisis/support safety messaging.
- **Age strategy (MVP)**: Use one safety policy for all users (no age-differentiated behavior and no age-gating flow).
- **Repeated high-risk incident rule**: If a session reaches 3+ high-risk turns, keep crisis template responses and suppress normal conversational replies for the rest of that session.
- **LLM provider**: Claude.
- **MVP storage scope**: Remove consent and conversation storage from MVP; use ephemeral handling only. Revisit storage as a post-MVP feature.

## Pending

- None.
