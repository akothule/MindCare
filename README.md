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
- Test command: `python3 -m pytest -q` (current suite covers API contract + Phase 2 safety/fallback behavior).

## Project docs (start here)

### Core docs
- `docs/DESIGN_DOC.md` - Product scope, MVP requirements, non-goals, and system overview.
- `docs/IMPLEMENTATION_PLAN.md` - Phase-by-phase execution plan from setup to post-MVP.
- `docs/SAFETY_POLICY.md` - Enforceable safety rules, risk handling logic, and policy overrides.
- `docs/CRISIS_COPY.md` - Fixed crisis/support message templates and resource wording.
- `docs/API_CONTRACT.md` - `/api/v1/chat` request/response schema and runtime behavior contract.

### Supporting docs
- `docs/DEV_COMMANDS.md` - Common commands (venv, uvicorn, curl, Render).
- `docs/TEST_PROMPT_CORPUS.json` - Starter safety regression prompts for policy/testing checks.
- `docs/DECISIONS_LOG.md` - Record of product/safety decisions and scope changes over time.
- `docs/CLAUDE_PROVIDER_CHECKLIST.md` - Pre-integration checklist for Claude model and ops settings.
- `docs/MVP_ACCEPTANCE_CHECKLIST.md` - Pass/fail release checklist to decide MVP demo readiness.
- `docs/POST_MVP_BACKLOG.md` - Deferred features and roadmap items intentionally out of MVP scope.

MindCare Presentation: https://docs.google.com/presentation/d/1feoDwCrOprOw1nQVuyknNRf32xba-9EXhhBKGKqM88g/edit?usp=sharing

MindCare Demo: https://ayush.kothule.me/mindcare

Youtube Demo: https://youtu.be/c-lSNw5wdKQ
