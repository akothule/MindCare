# MindCare
MindCare is an AI supportive companion for emotional reflection and basic coping guidance.

It is not a therapist or emergency service and does not provide diagnosis or medication advice.

## Current backend status

- Backend routes live: `GET /`, `GET /health`, `POST /api/v1/chat`.
- Deterministic safety layer is active in `/api/v1/chat`:
  - pre-LLM high routing: policy → `high_policy_template`; unmistakable first-person crisis → `high_template`; ambiguous crisis keywords → one safety classifier call (when enabled) for `high_template` vs `high_supporter_template`; all skip the **chat** LLM
  - optional **`MINDCARE_USE_LLM_ROUTER`**: a **single** `classify_safety_turn` (e.g. Haiku) merges pre-chat risk; with the flag on, legacy **medium** phrase regex is **disabled** and medium vs low comes from the classifier; with the flag off, regex medium still feeds merge + LLM hints
  - post-LLM unsafe-output override
  - parser fallback path (`200` with `policy_action="fallback"`)
  - repeated high-risk session lock after 3+ high-risk turns
- Automated tests: `python3 -m pytest -q` (routing and mocks; does not judge real LLM prose).
- Manual / live responses: `docs/MANUAL_TEST_PROMPTS.md` and `python scripts/sample_chat_responses.py` against a running API.

## Phase 3 (standalone frontend) — status

- **Implementation (local / repo):** **Complete.** UI lives in **`web/`** (Vite + React + TypeScript): branded single page, chat to `POST /api/v1/chat`, `session_id` in browser storage, crisis resources banner on medium/high-risk replies, typed client and `npm run build` output under `web/dist/`. Details: `docs/IMPLEMENTATION_PLAN.md` § Phase 3, `web/README.md`.
- **Stack choices:** Frontend host **Vercel** (public URL; env-based `VITE_API_BASE_URL` to the API); API on **Render** (CORS must allow Vercel production and local Vite, typically `http://localhost:5173`).
- **Shipping:** Deploying `web/dist` to Vercel and validating HTTPS + CORS in production is a separate ops step from “Phase 3 done” in code.

**Local dev:** start the API (`uvicorn` — see `docs/DEV_COMMANDS.md`), then in `web/` create/update `.env` manually from `.env.example`, run `npm install`, and `npm run dev`.

## Project docs (start here)

### Core docs
- `docs/DESIGN_DOC.md` - Product scope, MVP requirements, non-goals, and system overview (**v0.2** — includes optional safety router and template paths).
- `docs/IMPLEMENTATION_PLAN.md` - Phase-by-phase execution plan from setup to post-MVP (Phase 2 safety + router behavior updated to match code).
- `docs/SAFETY_POLICY.md` - Enforceable safety rules, risk handling logic, and policy overrides.
- `docs/CRISIS_COPY.md` - Fixed crisis/support message templates and resource wording.
- `docs/API_CONTRACT.md` - `/api/v1/chat` request/response schema and runtime behavior contract.

### Supporting docs
- `docs/BACKEND_CHAT_ROUTING.md` - How the backend handles `/api/v1/chat` today (pre-LLM rules, Claude merge, templates, responses).
- `web/README.md` - Phase 3 UI: install, dev server, build output.
- `docs/DEV_COMMANDS.md` - Common commands (venv, uvicorn, curl, Render).
- `docs/TEST_PROMPT_CORPUS.json` - Starter safety regression prompts for policy/testing checks.
- `docs/DECISIONS_LOG.md` - Record of product/safety decisions and scope changes over time.
- `docs/CLAUDE_PROVIDER_CHECKLIST.md` - Pre-integration checklist for Claude model and ops settings.
- `docs/MVP_ACCEPTANCE_CHECKLIST.md` - Pass/fail release checklist to decide MVP demo readiness.
- `docs/LLM_SAFETY_ROUTER_PLAN.md` - LLM-assisted safety routing (Phases 1–4 implemented behind `MINDCARE_USE_LLM_ROUTER`; see `.env.example` and `BACKEND_CHAT_ROUTING.md`).
- `docs/POST_MVP_BACKLOG.md` - Deferred features and roadmap items intentionally out of MVP scope.

MindCare Presentation: https://docs.google.com/presentation/d/1feoDwCrOprOw1nQVuyknNRf32xba-9EXhhBKGKqM88g/edit?usp=sharing

MindCare Old Demo (IBM Watson): https://ayush.kothule.me/mindcare

MindCare Current Demo (Anthropic API): https://mindcare-blush-six.vercel.app/
