# MindCare MVP Acceptance Checklist

Use this checklist to decide whether MVP is ready for first demo/use.

## Current status snapshot (2026-05-03)

- Backend and MVP Gate 2 policy behavior are implemented and covered by pytest.
- App-level chat rate limiting is implemented at 20 requests per 5 minutes per session and per hashed IP, with `429` responses when exceeded.
- Standalone Phase 3 UI is implemented in **`web/`** (Vite + React + TypeScript); production deploy to Vercel is a separate step when you are ready.

Checkboxes marked `[x]` below reflect verification against this repository and `python3 -m pytest -q` (plus code review for logging and `.gitignore`), except where the line explicitly requires the live frontend or human sign-off.

## Release gate

- [ ] All "must pass" checks in this file are completed.
- [ ] Any deferred items are documented in `docs/DECISIONS_LOG.md`.
- [ ] Team decision recorded: MVP is approved for demo.

## MVP Gate 1 - Backend foundation (must pass)

- [x] `GET /health` returns success when backend is running.
- [x] `POST /api/v1/chat` accepts valid payload from `docs/API_CONTRACT.md`.
- [x] Invalid requests return correct errors (`400`, `429`, `500`, `503` as applicable).
- [x] If `session_id` is missing, server returns a generated `session_id`.
- [x] Response includes required fields: `session_id`, `request_id`, `reply_text`, `risk_level`, `policy_action`, `latency_ms`.

## MVP Gate 2 - Safety and policy enforcement (must pass)

- [x] High-risk inputs return fixed crisis template from `docs/CRISIS_COPY.md` (no improvisation).
- [x] Medium-risk inputs return supportive escalation behavior and resources.
- [x] Low-risk inputs return normal supportive behavior.
- [x] Location disclaimer line is included in crisis/support safety messaging.
- [x] Disallowed content requests are blocked/redirected safely (no harmful instructions, no dosing guidance).
- [x] If model output is malformed or unsafe, system returns safe fallback with `policy_action=fallback`.

## MVP Gate 3 - Incident handling (must pass)

- [x] MVP uses one safety policy for all users (no age-differentiated behavior).
- [x] After 3+ high-risk turns in a session, normal conversational replies are suppressed.
- [x] In 3+ high-risk mode, crisis template responses continue.
- [ ] UI keeps a persistent crisis resources banner visible after high-risk responses.

## MVP Gate 4 - Frontend integration and UX checks (must pass for demo)

- [ ] User can send/receive messages end-to-end.
- [ ] Frontend persists `session_id` locally for active session continuity.
- [ ] Risk-triggered UI behavior works (banner shown on high risk).
- [ ] Frontend handles backend errors gracefully without breaking session.

## MVP Gate 5 - Reliability, observability, and security (must pass)

- [x] Safe retry-later fallback appears when LLM is unavailable.
- [x] No uncaught server errors for core happy path and known safety tests.
- [ ] p95 end-to-end `/api/v1/chat` latency meets MVP target (<= 8s) in local/staging test conditions.
- [x] Each request has a `request_id` for traceability.
- [x] Logs include policy-relevant fields (`risk_level`, `policy_action`, and fallback reason when used).
- [x] High-risk events are visible in logs for manual review.
- [x] No API keys or secrets are committed in repo.
- [ ] `.env` and secret-loading flow are verified for local development.
- [x] Basic input size/rate controls are enabled.
- [x] Core prompts in `docs/TEST_PROMPT_CORPUS.json` are exercised manually or by tests.
- [x] All high-risk corpus cases return `policy_action=high_template`.
- [x] Corpus parse-failure case returns `policy_action=fallback`.

## Optional post-MVP checks (not required now)

- [ ] Persistence and consent behavior implemented.
- [ ] Retention policy enforced.
- [ ] Dashboard alerts and advanced monitoring.
