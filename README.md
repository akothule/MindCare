# MindCare
MindCare is an AI supportive companion for emotional reflection and basic coping guidance.

It is not a therapist or emergency service and does not provide diagnosis or medication advice.

## Current backend status

- Backend routes live: `GET /`, `GET /health`, `POST /api/v1/chat`.
- Deterministic safety layer is active in `/api/v1/chat`:
  - pre-LLM risk routing for medium/high patterns
  - fixed medium/high templates with location disclaimer
  - post-LLM unsafe-output override
  - parser fallback path (`200` with `policy_action="fallback"`)
  - repeated high-risk session lock after 3+ high-risk turns
- Test command: `python3 -m pytest -q` (API contract, Phase 2 safety/fallback, session lock, post-LLM override, and app-level rate limiting).

## Phase 3 (standalone frontend) — status

- **Implementation (local / repo):** **Complete.** UI lives in **`web/`** (Vite + React + TypeScript): branded single page, chat to `POST /api/v1/chat`, `session_id` in browser storage, crisis resources banner on medium/high-risk replies, typed client and `npm run build` output under `web/dist/`. Details: `docs/IMPLEMENTATION_PLAN.md` § Phase 3, `web/README.md`.
- **Stack choices:** Frontend host **Vercel** (public URL; env-based `VITE_API_BASE_URL` to the API); API on **Render** (CORS must allow Vercel production and local Vite, typically `http://localhost:5173`).
- **Shipping:** Deploying `web/dist` to Vercel and validating HTTPS + CORS in production is a separate ops step from “Phase 3 done” in code.

**Local dev:** start the API (`uvicorn` — see `docs/DEV_COMMANDS.md`), then in `web/` create/update `.env` manually from `.env.example`, run `npm install`, and `npm run dev`.

## Project docs (start here)

### Core docs
- `docs/DESIGN_DOC.md` - Product scope, MVP requirements, non-goals, and system overview.
- `docs/IMPLEMENTATION_PLAN.md` - Phase-by-phase execution plan from setup to post-MVP.
- `docs/SAFETY_POLICY.md` - Enforceable safety rules, risk handling logic, and policy overrides.
- `docs/CRISIS_COPY.md` - Fixed crisis/support message templates and resource wording.
- `docs/API_CONTRACT.md` - `/api/v1/chat` request/response schema and runtime behavior contract.

### Supporting docs
- `web/README.md` - Phase 3 UI: install, dev server, build output.
- `docs/DEV_COMMANDS.md` - Common commands (venv, uvicorn, curl, Render).
- `docs/TEST_PROMPT_CORPUS.json` - Starter safety regression prompts for policy/testing checks.
- `docs/DECISIONS_LOG.md` - Record of product/safety decisions and scope changes over time.
- `docs/CLAUDE_PROVIDER_CHECKLIST.md` - Pre-integration checklist for Claude model and ops settings.
- `docs/MVP_ACCEPTANCE_CHECKLIST.md` - Pass/fail release checklist to decide MVP demo readiness.
- `docs/POST_MVP_BACKLOG.md` - Deferred features and roadmap items intentionally out of MVP scope.

MindCare Presentation: https://docs.google.com/presentation/d/1feoDwCrOprOw1nQVuyknNRf32xba-9EXhhBKGKqM88g/edit?usp=sharing

MindCare Demo: https://ayush.kothule.me/mindcare

Youtube Demo: https://youtu.be/c-lSNw5wdKQ
