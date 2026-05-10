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
- **Prompt-injection / jailbreak routing (MVP)**: Treat as high-risk safety concern; use `policy_action` `high_policy_template` (refusal copy with 988), distinct from ideation `high_template`. Reserve `blocked` for other product-specific cases if needed later.
- **LLM provider**: Claude.
- **MVP storage scope**: Remove consent and conversation storage from MVP; use ephemeral handling only. Revisit storage as a post-MVP feature.

## 2026-03-28 (docs + hosting)

- **MVP backend hosting**: [Render](https://render.com) web service for the FastAPI app (deploy after the API runs locally and the repo is connected to Git).
- **Crisis copy composition**: Clarified that high/medium template bodies (§1/§2 in `CRISIS_COPY.md`) are fixed verbatim and the location disclaimer (§5) is always appended to the same message—no conflict with “exact” wording.
- **API contract**: Renamed from “Draft” to locked MVP contract title in `API_CONTRACT.md`.
- **Test corpus**: Documented jailbreak / harm-seeking → `high_policy_template`; ideation → `high_template`; `schema_001` harness-only for mocked parser/LLM failures.
- **Decisions captured**: Rate limit and prompt-injection routing recorded here for traceability.

## 2026-04-28 (Phase 2 readiness lock)

- **Fallback HTTP behavior**: For policy-safe fallbacks (including malformed model output), return `200` with `policy_action="fallback"` and a populated `fallback_reason`. Reserve `500/503` for infrastructure/runtime failures where a contract-shaped fallback cannot be produced.
- **Deterministic policy order**: Enforce this precedence in `/api/v1/chat`: validate/normalize input -> pre-LLM risk rules -> session state check (including 3+ high-risk lock) -> LLM generation when allowed -> post-LLM safety filter -> final policy override/template selection -> response + structured logging.
- **Template mapping**: `medium_template`, `high_template`, and `high_policy_template` use fixed copy from `docs/CRISIS_COPY.md`; append the location disclaimer line in the same message.
- **Observability minimum fields**: Each turn log should include `request_id`, `session_id`, final `risk_level`, final `policy_action`, `fallback_reason` (when present), and `trigger_source` (`pre_llm`, `llm`, `post_llm`, `session_lock`, `fallback`).

## 2026-04-28 (Phase 2 implementation milestone)

- **Safety layer status**: Implemented deterministic safety/fallback behavior in backend chat handler and validated with automated pytest coverage.
- **Session incident handling**: Added in-memory high-risk turn counting and 3+ high-risk session lock behavior for MVP.
- **Test posture**: Converted early Phase 2 checks into active tests for medium/high template routing, fallback path, post-LLM override, and session lock.
- **Outstanding MVP gap**: Rate limiting remained pending at this milestone and required completion before final MVP acceptance sign-off.

## 2026-05-02 (Rate limiting implementation complete)

- **MVP rate limiting status**: Implemented app-level chat rate limiting at 20 requests per 5 minutes per session and per hashed IP.
- **HTTP behavior**: When chat rate limits are exceeded, `/api/v1/chat` returns `429` with a retry-later message.
- **Verification**: Added automated pytest coverage for both per-session and per-IP throttling behavior.

## 2026-05-03 (Phase 3 web stack finalized)

- **Phase 3 UI toolchain**: Vite + React + TypeScript for the standalone public page (build, components, typed API client).
- **Phase 3 frontend hosting**: Vercel (HTTPS, CDN, previews, optional custom domain).
- **API hosting**: Render for the FastAPI service (aligned with existing MVP backend decision); secrets stay server-side.
- **Integration**: Browser calls Render from the Vercel origin; CORS allowlist must include Vercel production and local Vite dev; frontend uses env-based API base URL (e.g. `VITE_API_BASE_URL`).

## 2026-05-03 (Phase 3 local implementation complete)

- **In-repo deliverable**: The **`web/`** SPA implements the Phase 3 scope in `docs/IMPLEMENTATION_PLAN.md` for local development and production builds (`npm run build` → `web/dist/`).
- **Not bundled in “local complete”**: Hosting the static build on Vercel (or equivalent) and end-to-end verification on production URLs remain operational follow-ups; they do not block treating Phase 3 **code** as done in this repository.

## 2026-05-03 (`/chat` pipeline debug logging)

- **Flag**: `MINDCARE_CHAT_DEBUG` in repo-root `.env` (documented in `.env.example` and `docs/DEV_COMMANDS.md`).
- **Output**: Multiline `[chat-debug]` summaries per successful chat request at **WARNING**, so they appear with uvicorn default logging without a custom handler. May include a short user message preview; keep disabled in production unless you accept that in logs.

## 2026-05-09 (Safety policy: LLM router merge semantics)

- **`merged_pre_chat` vs reply JSON**: Documented in `docs/SAFETY_POLICY.md` §4 that pre-chat merge (hard gates + optional classifier + soft regex) produces `merged_pre_chat`, then `final_risk = max(merged_pre_chat, reply_json.risk_level)` so the reply model cannot downgrade pre-chat routing but may escalate.
- **Classifier reliability**: Aligned §4/§5 with `docs/LLM_SAFETY_ROUTER_PLAN.md` §3.2 — v1 `confidence` enum, fallback when low/missing/invalid, rationale logging off by default in production.
- **Logging**: Extended §8 minimum fields with optional `merged_pre_chat_risk`, `classifier_risk_level`, `classifier_confidence`, and router-enabled flag for audit when the dedicated classifier ships.
- **Policy version**: Bumped safety policy doc title to **v0.2** for this edit.
- **Pipeline ordering**: `docs/SAFETY_POLICY.md` §4 now places the **§11 session lock** immediately after hard pre-checks so a locked session skips classifier and chat LLM, matching the intent of the existing handler.

## 2026-05-09 (LLM safety router Phase 1 skeleton)

- **Flag default**: `MINDCARE_USE_LLM_ROUTER` defaults to **false** so production and existing tests see no extra Anthropic call and no routing change.
- **Phase 1 scope**: When the flag is true, the handler runs a dedicated classifier completion (validated `SafetyClassificationPayload`) on the LLM-eligible path only (after session lock and pre-LLM high gates). **Merge into `pre_risk` / templates is Phase 2**; Phase 1 only logs `merged_pre_chat_preview = max(pre_risk, classifier.risk_level)` for observability.
- **Classifier model**: Optional `MINDCARE_CLASSIFIER_MODEL`; if unset, the main `ANTHROPIC_MODEL` is used.
- **Failure behavior (Phase 1)**: Classifier parse/API/network errors are logged; the chat completion still runs so users are not blocked by classifier outages.

## 2026-05-09 (LLM safety router Phase 2 merge)

- **`merged_pre_chat`**: Implemented in `mindcare/safety_merge.py` and wired in `mindcare/routers/chat.py`. Trusted classifier uses `max(pre_risk, classifier.risk_level)`; missing/low-confidence classifier uses regex-only soft routing on the LLM path; trusted `merged_pre_chat == high` skips the chat LLM and selects crisis vs policy template from classifier `recommended_action`.
- **Tests**: Default `MINDCARE_USE_LLM_ROUTER=false` in pytest autouse so local `.env` cannot enable the real classifier during tests; added `tests/test_safety_merge.py` and API tests for classifier-high short-circuit and low-confidence fallback.
- **Policy version**: Bumped `docs/SAFETY_POLICY.md` title to **v0.3** for Phase 2 merge documentation.

## 2026-05-09 (LLM safety router Phase 3 — regex medium as classifier hints)

- **Choice**: Router-plan **Option A** — keep medium regex as **signals** to the classifier (and chat LLM) only when `MINDCARE_USE_LLM_ROUTER` is true; trusted merge uses baseline `low` when `pre_risk` was **only** regex-medium so the classifier can route low without being overridden by heuristics. Soft fallback unchanged (full regex `pre_risk`).
- **Code**: `mindcare/llm.py` (`apply_internal_routing_notes`, classifier `pre_medium_signals`); `mindcare/safety_merge.py` (trusted baseline strip); `mindcare/routers/chat.py` (pass hints, fix medium `trigger_source` when merge differs from regex).
- **Policy version**: `docs/SAFETY_POLICY.md` **v0.4**.

## 2026-05-09 (Soft empathy hints — low merge + distress heuristics)

- **Behavior**: When `MINDCARE_USE_LLM_ROUTER` is on and a trusted classifier merges **low** while regex **medium** heuristics fired, the chat completion receives **short categorical cues** and a dedicated internal calibration block (`mindcare/llm.py`: `apply_soft_empathy_calibration`) — not the full `pre_medium_signals` medium path — so `policy_action` stays **normal** while nudging tone. Opt out with `MINDCARE_SOFT_EMPATHY_HINTS=false`.
- **Policy version**: `docs/SAFETY_POLICY.md` **v0.5**.

## 2026-05-09 (LLM safety router Phase 4 — evals & tests)

- **Corpus:** `docs/TEST_PROMPT_CORPUS.json` **v0.2** — Phase 4 `class_*` cases (third-party, educational, negation, meta, third-party+suicide keyword).
- **Tests:** `tests/test_phase4_classifier_routing.py` (mocked classifier + baseline router-off checks); `tests/test_integration_chat.py` opt-in live smoke (`MINDCARE_RUN_INTEGRATION=1`, skipped when `CI=true`).
- **Tooling:** `pytest.ini` registers `integration` marker; `scripts/sample_chat_responses.py --include-phase4-corpus`; `docs/DEV_COMMANDS.md` / `docs/MANUAL_TEST_PROMPTS.md` updated.

## 2026-05-09 (Router on: legacy medium regex retired; single Haiku soft tier)

- **Pre-LLM:** When `MINDCARE_USE_LLM_ROUTER` is true, `_MEDIUM_PATTERNS` are not evaluated; `pre_risk` is `low` or `high` (hard gates unchanged). Medium vs low comes only from `classify_safety_turn` (same Haiku as routing).
- **Soft empathy:** When merge is low and the router is on, cues use classifier `intent_bucket` (`distress`, `ambiguous_distress`, `hopelessness`) instead of requiring regex medium hits. Router off keeps regex medium + prior merge behavior.
- **Crisis §1 vs §1a:** Ambiguous crisis keywords use one `classify_safety_turn` for `high_template` vs `high_supporter_template` (no separate perspective model).
- **Docs/tests:** `docs/TEST_PROMPT_CORPUS.json` v0.3 notes; `docs/SAFETY_POLICY.md` **v0.6** §4; `docs/BACKEND_CHAT_ROUTING.md`, `docs/LLM_SAFETY_ROUTER_PLAN.md`, `README.md`, `docs/MANUAL_TEST_PROMPTS.md`, `docs/DEV_COMMANDS.md`, `docs/MVP_ACCEPTANCE_CHECKLIST.md`, **`docs/DESIGN_DOC.md` v0.2**, **`docs/IMPLEMENTATION_PLAN.md`** Phase 2 status; `tests/test_phase4_classifier_routing.py` extended.

## Pending

- None.
