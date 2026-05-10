# MindCare — developer commands

Run these from the **repository root** (the directory that contains `mindcare/` and `requirements.txt`).

## First-time setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create or update `.env` manually using `.env.example` as the template. Never commit `.env`.

Required for live chat responses: set **`ANTHROPIC_API_KEY`** in `.env` (see `.env.example`).

Optional tuning (defaults match `docs/API_CONTRACT.md`): **`MAX_MESSAGE_LENGTH`**, **`MAX_SESSION_TURNS`**, **`ANTHROPIC_MAX_TOKENS`**, **`EMPTY_REPLY_FALLBACK`**, **`MINDCARE_USE_LLM_ROUTER`**, **`MINDCARE_CLASSIFIER_MODEL`**, **`MINDCARE_SOFT_EMPATHY_HINTS`**, **`MINDCARE_CRISIS_PERSPECTIVE_LLM`** (see `.env.example` and `docs/BACKEND_CHAT_ROUTING.md`). Chat system prompt: **`mindcare/prompts/system.txt`**; safety classifier: **`mindcare/prompts/classifier_system.txt`** (edit and restart the server).

## Run the API locally

Bind address and port are passed to **uvicorn** (not read from `.env` by the app):

```bash
source .venv/bin/activate
uvicorn mindcare.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: `GET http://127.0.0.1:8000/` or `GET http://127.0.0.1:8000/health`
- Chat: `POST http://127.0.0.1:8000/api/v1/chat`

**Note:** `.env` is loaded from the **repo root** automatically (`mindcare/config.py`), even if your shell’s current directory differs slightly—still prefer running `uvicorn` from the repo root.

### Optional: `/chat` pipeline debug logs

Set **`MINDCARE_CHAT_DEBUG=true`** in the **repo-root** `.env` (not `web/.env`), then restart uvicorn. Each successful `POST /api/v1/chat` emits **`[chat-debug]`** blocks at **WARNING** (visible with uvicorn default log settings); see `mindcare/routers/chat.py`. Previews may include user text; keep the flag off in production. The separate `chat_policy_*` lines stay at **INFO** and may not show in the terminal unless you configure logging.

## Run the Phase 3 web UI locally (Vite)

Phase 3 UI **implementation** in this repo is complete; this section is how you run and build it locally (and produce `web/dist/` for static hosting).

From the repo root:

```bash
cd web
npm install               # first time only
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). Before starting the UI, create/update `web/.env` manually from `web/.env.example` and set `VITE_API_BASE_URL` (for local API, use `http://127.0.0.1:8000`). Also ensure **`MINDCARE_CORS_ORIGINS`** includes that UI origin (defaults in `mindcare/config.py` include port **5173**).

### Quick `curl` checks

```bash
curl -s http://127.0.0.1:8000/
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hello"}'
```

With a session:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id": "YOUR-SESSION-UUID", "message": "Thanks for listening."}'
```

### Sample chat responses (script)

With the API running from the repo root, you can POST a fixed set of scenarios and print full JSON responses (see also `docs/MANUAL_TEST_PROMPTS.md`):

```bash
python scripts/sample_chat_responses.py
```

Other origins and extras:

```bash
python scripts/sample_chat_responses.py --base-url http://127.0.0.1:8000
python scripts/sample_chat_responses.py --include-session-lock
```

Default base URL is **`MINDCARE_API_BASE`** if set, otherwise `http://127.0.0.1:8000`.

If **`ANTHROPIC_API_KEY`** is unset, chat returns **503** (LLM unavailable).

### Troubleshooting chat errors

- **`503` with billing / quota / invalid model:** Add credits or a payment method in the [Anthropic console](https://console.anthropic.com/) if the account requires it, and confirm **`ANTHROPIC_MODEL`** matches a model your key can use (copy the id from the console or docs).
- **`401`:** Wrong or revoked API key.
- **`404` on model:** Wrong model string; try the default in `.env.example` or pick a model from Anthropic’s model list.
- **Restart `uvicorn` after editing `.env`** so settings reload.

Server logs now include the **Anthropic status code and body** for API errors (see the terminal where `uvicorn` runs).

## Lint / sanity checks (optional)

```bash
python3 -m compileall -q mindcare
```

## Test suite

```bash
python3 -m pytest -q
```

**Phase 4 — opt-in live API check** (not for CI; requires `ANTHROPIC_API_KEY` and repo-root `.env` if you use it):

```bash
export MINDCARE_RUN_INTEGRATION=1
python3 -m pytest -q tests/test_integration_chat.py -m integration
```

**Classifier-focused sample prompts** (running API with real models):

```bash
python scripts/sample_chat_responses.py --include-phase4-corpus
```

Current coverage highlights:
- `tests/test_api.py`: health endpoints, request validation, baseline contract shape, high-risk fixed template, parser fallback 200 behavior, per-session and per-IP rate limits.
- `tests/test_phase2_safety.py`: corpus-driven safety routing, low-risk mocked normal path, repeated high-risk session lock, post-LLM unsafe-output override.
- `tests/test_phase4_classifier_routing.py`: Phase 4 corpus IDs (`class_*`) baseline + mocked LLM-router merge paths.
- `tests/test_integration_chat.py`: optional live `/chat` smoke (`MINDCARE_RUN_INTEGRATION=1`, skipped on `CI`).

## Render (production-style host)

Typical **Start command** (Render sets **`PORT`**):

```bash
uvicorn mindcare.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Set the same environment variables as in `.env.example` in the Render dashboard (**Environment**). Do not commit secrets to the repo.

## Related docs

- API shape: `docs/API_CONTRACT.md`
- Safety behavior (Phase 2+): `docs/SAFETY_POLICY.md`
