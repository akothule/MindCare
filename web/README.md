# MindCare web (Phase 3)

Vite + React + TypeScript UI for `POST /api/v1/chat`.

## Setup

```bash
npm install
```

Create or update `web/.env` manually from `web/.env.example` before running commands.

## Develop

```bash
npm run dev
```

Run the FastAPI app from the repo root first (see `docs/DEV_COMMANDS.md`). Set `VITE_API_BASE_URL` in `.env` to match (e.g. `http://127.0.0.1:8000`).

## Build

```bash
npm run build
```

Static output is in `dist/` (for Vercel or any static host).
