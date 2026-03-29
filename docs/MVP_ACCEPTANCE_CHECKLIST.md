# MindCare MVP Acceptance Checklist

Use this checklist to decide whether MVP is ready for first demo/use.

## Release gate

- [ ] All "must pass" checks in this file are completed.
- [ ] Any deferred items are documented in `docs/DECISIONS_LOG.md`.
- [ ] Team decision recorded: MVP is approved for demo.

## Phase 1 - Backend foundation (must pass)

- [ ] `GET /health` returns success when backend is running.
- [ ] `POST /api/v1/chat` accepts valid payload from `docs/API_CONTRACT.md`.
- [ ] Invalid requests return correct errors (`400`, `429`, `500`, `503` as applicable).
- [ ] If `session_id` is missing, server returns a generated `session_id`.
- [ ] Response includes required fields: `session_id`, `request_id`, `reply_text`, `risk_level`, `policy_action`, `latency_ms`.

## Phase 2 - Safety and policy enforcement (must pass)

- [ ] High-risk inputs return fixed crisis template from `docs/CRISIS_COPY.md` (no improvisation).
- [ ] Medium-risk inputs return supportive escalation behavior and resources.
- [ ] Low-risk inputs return normal supportive behavior.
- [ ] Location disclaimer line is included in crisis/support safety messaging.
- [ ] Disallowed content requests are blocked/redirected safely (no harmful instructions, no dosing guidance).
- [ ] If model output is malformed or unsafe, system returns safe fallback with `policy_action=fallback`.

## Phase 3 - Incident handling (must pass)

- [ ] MVP uses one safety policy for all users (no age-differentiated behavior).
- [ ] After 3+ high-risk turns in a session, normal conversational replies are suppressed.
- [ ] In 3+ high-risk mode, crisis template responses continue.
- [ ] UI keeps a persistent crisis resources banner visible after high-risk responses.

## Phase 4 - Frontend integration and UX checks (must pass for demo)

- [ ] User can send/receive messages end-to-end.
- [ ] Frontend persists `session_id` locally for active session continuity.
- [ ] Risk-triggered UI behavior works (banner shown on high risk).
- [ ] Frontend handles backend errors gracefully without breaking session.

## Phase 5 - Reliability, observability, and security (must pass)

- [ ] Safe retry-later fallback appears when LLM is unavailable.
- [ ] No uncaught server errors for core happy path and known safety tests.
- [ ] p95 end-to-end `/api/v1/chat` latency meets MVP target (<= 8s) in local/staging test conditions.
- [ ] Each request has a `request_id` for traceability.
- [ ] Logs include policy-relevant fields (`risk_level`, `policy_action`, and fallback reason when used).
- [ ] High-risk events are visible in logs for manual review.
- [ ] No API keys or secrets are committed in repo.
- [ ] `.env` and secret-loading flow are verified for local development.
- [ ] Basic input size/rate controls are enabled.
- [ ] Core prompts in `docs/TEST_PROMPT_CORPUS.json` are exercised manually or by tests.
- [ ] All high-risk corpus cases return `policy_action=high_template`.
- [ ] Corpus parse-failure case returns `policy_action=fallback`.

## Optional post-MVP checks (not required now)

- [ ] Persistence and consent behavior implemented.
- [ ] Retention policy enforced.
- [ ] Dashboard alerts and advanced monitoring.
