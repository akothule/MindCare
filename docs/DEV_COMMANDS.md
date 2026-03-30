# MindCare — developer commands

Run these from the **repository root** (the directory that contains `mindcare/` and `requirements.txt`).

## First-time setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then edit .env — never commit .env
```

Required for live chat responses: set **`ANTHROPIC_API_KEY`** in `.env` (see `.env.example`).

Optional tuning (defaults match `docs/API_CONTRACT.md`): **`MAX_MESSAGE_LENGTH`**, **`MAX_SESSION_TURNS`**, **`ANTHROPIC_MAX_TOKENS`**, **`EMPTY_REPLY_FALLBACK`**. The system prompt text lives in **`mindcare/prompts/system.txt`** (edit and restart the server).

## Run the API locally

Bind address and port are passed to **uvicorn** (not read from `.env` by the app):

```bash
source .venv/bin/activate
uvicorn mindcare.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: `GET http://127.0.0.1:8000/`
- Chat: `POST http://127.0.0.1:8000/api/v1/chat`

**Note:** `.env` is loaded from the **repo root** automatically (`mindcare/config.py`), even if your shell’s current directory differs slightly—still prefer running `uvicorn` from the repo root.

### Quick `curl` checks

```bash
curl -s http://127.0.0.1:8000/

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

## Render (production-style host)

Typical **Start command** (Render sets **`PORT`**):

```bash
uvicorn mindcare.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Set the same environment variables as in `.env.example` in the Render dashboard (**Environment**). Do not commit secrets to the repo.

## Related docs

- API shape: `docs/API_CONTRACT.md`
- Safety behavior (Phase 2+): `docs/SAFETY_POLICY.md`
