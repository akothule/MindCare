# MindCare Implementation Plan

## Pre-coding deliverables (required before Phase 1)

Before backend implementation starts, finalize these source-of-truth artifacts:

- `docs/SAFETY_POLICY.md` (policy behavior, risk tiers, deterministic safety pipeline)
- `docs/CRISIS_COPY.md` (approved medium/high templates and resource wording)
- `docs/API_CONTRACT.md` (`/api/v1/chat` request/response, fallback and observability fields)
- `docs/TEST_PROMPT_CORPUS.json` (starter safety regression prompts)
- `docs/BACKEND_CHAT_ROUTING.md` (concrete `/chat` order of operations; keep in sync with code)
- `docs/LLM_SAFETY_ROUTER_PLAN.md` (optional dedicated safety classifier and rollout)

And finalize open product decisions:
- None (MVP defaults are captured in `docs/DECISIONS_LOG.md`).

These should be treated as required inputs to implementation and testing.
Record all finalized choices in `docs/DECISIONS_LOG.md`.

## Phase 0 – Foundations and scope

* Define MindCare’s role: “supportive companion, not a therapist; no diagnosis; no emergency help.”  
* Decide on hosting for backend (e.g., Render, Railway, Fly.io, or a VM). Optionally preselect a managed Postgres/Firestore for post-MVP persistence, but do not implement DB work in MVP.  
* Use Claude as the initial LLM provider and get API keys; confirm ongoing compliance with mental‑health–adjacent safety guardrails.

**Output:** a short design doc (even 1–2 pages) capturing goals, limits, and dependencies so you don’t re‑decide basics later.

## Phase 1 – FastAPI backend skeleton

1. Project setup  
* Create a repo, set up virtual environment and dependencies: fastapi, uvicorn, pydantic, HTTP client (e.g., httpx), and your LLM SDK.  
* Configure environment variables for secrets (LLM keys) using python-dotenv or your host’s secret manager.  
* set up .env \+ .gitignore so that LLM keys are never committed to repo.  
2. Basic FastAPI app  
* Create main.py with:  
  * Root route / (health check).  
  * Versioned API prefix /api/v1.  
* Add CORS middleware allowing your eventual frontend origin(s).  
3. ​Core /chat endpoint (first version)  
* Request model: session\_id, message, metadata (optional user agent, locale).  
* Response model: reply\_text, risk\_level ("low" | "medium" | "high"), policy\_action, fallback\_reason (optional string).  
* Inside handler:  
  * (For now) keep an in‑memory dict from session\_id → last N messages.  
    * In-memory storage is lost on server restart; replace before any real user testing.  
  * Build an LLM prompt with system \+ conversation history \+ latest user message.  
  * Call the LLM, parse structured JSON.  
* Input validation:  
  * max message length  
  * reject empty/null messages  
  * sanitize strings before passing to LLM.

    

**​Output:** running backend you can hit with curl/Postman and get a reasonable text reply.

## Phase 2 – Safety and guardrails

**Status (repo, 2026-05):** Implemented in `mindcare/routers/chat.py`, `mindcare/llm.py`, `mindcare/safety_merge.py`. Policy detail: `docs/SAFETY_POLICY.md` **v0.6**; routing steps: `docs/BACKEND_CHAT_ROUTING.md`.

1. Pre‑LLM safety checks  
* **Hard gates (regex):** injection, harm-how-to, crisis keyword lists, and inherently first-person self-harm phrases → fixed templates where required; **no** conversational LLM on those paths when policy short-circuits.  
* **Optional `MINDCARE_USE_LLM_ROUTER`:** `classify_safety_turn` (typically Haiku via `MINDCARE_CLASSIFIER_MODEL`) produces `merged_pre_chat` with `merge_pre_chat_risk`. When the flag is **on**, legacy **medium** phrase regex is **not** used in pre-LLM classification—medium vs low comes from the classifier.  
* **Ambiguous crisis keywords** (e.g. third-party + suicide): one `classify_safety_turn` when `MINDCARE_CRISIS_PERSPECTIVE_LLM` is enabled chooses **`high_template`** vs **`high_supporter_template`** (see `docs/CRISIS_COPY.md` §1 / §1a).  
* Log high-risk outcomes; **session lock** after 3+ high-risk turns (crisis template only for subsequent messages in that session).

2. System prompts and policy  
* Chat system prompt: `mindcare/prompts/system.txt` — role, limits, JSON shape (`LLMStructuredPayload`).  
* Classifier system prompt: `mindcare/prompts/classifier_system.txt` — `SafetyClassificationPayload` (`risk_level`, `intent_bucket`, `recommended_action`, `confidence`).

3. Post‑LLM filters  
* Scan model `reply_text` for disallowed patterns; override with **`high_policy_template`** when matched.

4. Fixed crisis and support scripts  
* **§1** first-person high, **§1a** supporter / third-party high (`high_supporter_template`), **§1b** policy/refusal (`high_policy_template`), **§2** medium fallback — aligned with `docs/CRISIS_COPY.md`; bodies live in `chat.py` at runtime.  
* U.S. resource list (988, CTL, NAMI, 911) + location disclaimer behavior per contract.

5. Test the safety layer  
* Pytest corpus and classifier routing tests (`tests/test_phase2_safety.py`, `tests/test_phase4_classifier_routing.py`, `tests/test_safety_merge.py`, etc.); `docs/TEST_PROMPT_CORPUS.json` through **v0.3+**.

**Output:** `/api/v1/chat` returns policy‑compliant responses with explicit `risk_level` / `policy_action` / `resources`; optional router path documented for staging rollout (`docs/LLM_SAFETY_ROUTER_PLAN.md` Phase 5).

## Phase 3 – Minimal standalone frontend

**Implementation in this repo:** the app lives under **`web/`** (Vite + React + TypeScript). Local commands and env vars are described in `docs/DEV_COMMANDS.md` and `web/README.md`.

### Finalized tech stack (implementation)

| Layer | Choice | Role |
|------|--------|------|
| UI toolchain | **Vite** | Dev server, fast rebuilds, production bundling of JS/CSS/assets (`npm run dev` / `npm run build`). |
| UI library | **React** | Component model for chat, header, and crisis banner; scales to more screens without a rewrite. |
| Language | **TypeScript** | Types for API request/response shapes and UI state; catches mistakes before runtime. |
| Frontend host | **Vercel** | HTTPS, CDN, deploy previews, custom domain; serves the static/SPA build output. |
| API host | **Render** | Runs the FastAPI app (`/api/v1/chat`); holds secrets (e.g. LLM key); already the MVP backend target. |

**Why Vite + React + TypeScript together:** Vite handles *build tooling*; React handles *UI structure*; TypeScript handles *correctness* for anything that talks to your contract (`docs/API_CONTRACT.md`). You can add routes and components later (Phase 5–6) without replacing that trio.

**Cross-cutting (do not skip):**

* Frontend reads API base URL from env (e.g. `VITE_API_BASE_URL`); never hard-code production API URLs in source.
* Backend `mindcare_cors_origins` must include the Vercel production origin (and local Vite origin, typically `http://localhost:5173`, for development).
* Public marketing links (e.g. Rebrandly) point at the **Vercel** URL; the Render API URL is for `fetch` only.

1. Single-page experience  
* One **primary** public URL: branding (logo), title, tagline, short guidance, then chat (no third-party site shell).  
* Chat: message list, input, Send; `POST /api/v1/chat` with `session_id` in `localStorage`.  
* Risk UX: persistent resources banner when `risk_level` is medium or high, aligned with `docs/CRISIS_COPY.md` and API `resources`.  
2. Ship and verify  
* Build with Vite; deploy static output to **Vercel**; keep API on **Render**.  
* Confirm mobile layout, CORS, and error handling (`400`, `429`, `503`, etc.); HTTPS only (no mixed content).

**Output:** one shareable URL (Vercel) where users open MindCare, see your branding, and chat with the Render-hosted API.

**Status (2026-05-03, local):** The in-repo Phase 3 app under **`web/`** is implemented and buildable (Vite + React + TypeScript): single-page layout, chat against `POST /api/v1/chat`, `session_id` in `localStorage`, crisis resources banner for medium/high responses, and graceful handling of HTTP errors. The remaining step for the Phase 3 **output** above is **deploying** the static build (e.g. Vercel) and confirming CORS + HTTPS against the Render API.

## Phase 4 – Data layer and privacy (post-MVP)

1. DB selection and connection  
* Choose a hosted Postgres (e.g., Supabase/Neon) or Firestore.  
* ​In FastAPI, set up a DB connection pool (e.g., SQLAlchemy \+ async driver).  
2. Schema design (minimum viable)  
* users (or profiles) – optional, if you allow logins later; for now you can skip or keep anonymous.  
* sessions:  
  * id, created\_at, last\_active\_at, client\_metadata (device, locale), optional pseudonymous user ref.  
* messages:  
  * id, session\_id, role (user/assistant/system), text, risk\_level, created\_at.  
* events (optional, later): store high‑risk events, feedback (thumbs up/down), etc.  
3. Privacy  
* Do NOT store names, emails, or contact info initially.  
* Add a small “Data & Privacy” section on the site explaining current ephemeral handling and future storage plans.  
* If persistence is introduced later, add consent UX and retention policy first (docs, then implementation).
4. Wire FastAPI to DB  
* On first request without session\_id, create a new DB session and return its ID.  
* Persist each message+reply with timestamps and risk level.  
5. DB migrations tooling  
* Even at MVP scale, using something like Alembic (for SQLAlchemy) from the start means you don't have to manually alter tables later.

**Output:** persistence, consent, and retention become available after MVP launch.

## Phase 5 – Productizing and UX improvements

1. Refine conversation style  
* Review logs (especially non‑crisis chats) to see where the bot feels robotic.  
* Iterate on prompt: adjust length, add examples of good responses, tune how often it asks questions vs offers exercises.  
2. Add features safely  
* Short coping tools: grounding exercise, breathing guide, values clarification, etc. (still non‑therapeutic, framed as self‑help).  
* Simple “mood check‑ins” with a 1–5 scale stored per session/day.  
3. Feedback loop  
* UI buttons for “This was helpful / Not helpful” per reply; store in events.  
* Use these to spot prompt failures and edge cases.  
* Schedule a regular prompt review cycle (e.g., weekly) using stored feedback and conversation logs to iteratively improve the system prompt.  
4. ​Monitoring and observability  
* Add structured logging (request ID, session ID, risk level, response time).  
* Set up basic dashboards/alerts on high‑risk message frequency or error rates.

## Phase 6 – Dedicated web app (multi-page, richer UX)

1. Full web app  
* Build a Next.js or full React app with:  
  * Landing page (what MindCare is/isn’t, safety info).  
  * Chat page with better UI, avatar, conversation sections.  
  * Static pages: About, Data & Privacy, Resources.  
2. Optional accounts  
* If you ever add persistent user accounts, implement auth (e.g., passwordless email login or OAuth) and update schema to link sessions to users.  
* Re‑evaluate privacy/PHI risk before storing any contact info.  
3. Consolidate the product URL  
* Point your primary domain at the dedicated app; optionally keep a short redirect from any legacy URLs so bookmarks still work.

## Phase 7 – Evaluation and ethics

* Periodically review conversations (anonymized) against published mental‑health chatbot safety checklists and user‑experience studies, tweaking prompts and guardrails.  
  * Test against SAMHSA safe messaging guidelines.  
  * Evaluate at least one random sample of 20+ conversations for tone, safety compliance, and naturalness.  
  * Document any prompt changes and the rationale  
* Consider running small usability tests with friends/volunteers to get qualitative feedback on tone, clarity, and perceived safety.