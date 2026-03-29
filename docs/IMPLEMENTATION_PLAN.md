# MindCare Implementation Plan

## Pre-coding deliverables (required before Phase 1)

Before backend implementation starts, finalize these source-of-truth artifacts:

- `docs/SAFETY_POLICY.md` (policy behavior, risk tiers, deterministic safety pipeline)
- `docs/CRISIS_COPY.md` (approved medium/high templates and resource wording)
- `docs/API_CONTRACT.md` (`/api/v1/chat` request/response, fallback and observability fields)
- `docs/TEST_PROMPT_CORPUS.json` (starter safety regression prompts)

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

1. Pre‑LLM safety checks  
* Implement a simple risk classifier:  
  * Start with curated keyword/phrase lists for self‑harm/suicide, violence, and abuse.  
  * If triggered, set risk\_level="high" and skip normal LLM call or call LLM with a special “crisis reply” prompt.  
* Log all high‑risk messages separately for review.  
* Add repeated high-risk incident handling: when a session reaches 3+ high-risk turns, keep crisis responses and suppress normal conversation for the rest of that session.
2. System prompt and policy  
* Write a detailed system prompt for the LLM including:  
  * Role, tone, and limitations (no diagnosis, no meds advice).  
  * Required behavior in crisis (always recommend contacting emergency/hotline, trusted people, and professional support; avoid giving how‑to instructions).  
  * Output as JSON with fields you expect.

3. Post‑LLM filters  
* Scan LLM output for disallowed content (explicit instructions for self‑harm, medical dosing, hateful speech).  
* If found, trigger a safe fallback template instead of returning the raw answer.  
4. Fixed crisis scripts  
* Create templates for:  
  * Immediate risk (e.g., clear suicide intent).  
  * Medium risk (e.g., depressive statements without explicit plan).  
* Make them localized (at least U.S. numbers initially) and consistent with major advisory bodies.  
  * 988  
  * Crisis Text Line: text HOME to 741741  
  * NAMI: 1-800-950-6264  
5. Test the safety layer  
* Write a small test suite with known high-risk phrases and verify they always trigger the crisis template.

**Output:** /chat now always returns policy‑compliant responses with explicit risk flags.

## Phase 3 – Data layer and privacy (post-MVP)

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

## Phase 4 – Minimal frontend and Google Sites integration

1. Prototype chat frontend  
* Create a very simple HTML/JS or small React/Vite app:  
  * Text input, message list, “Send” button, typing indicator.  
  * It calls /api/v1/chat with session\_id (persisted in localStorage).  
* Handle risk flags visually (e.g., show a banner if risk\_level is medium/high).  
2. Host the frontend  
* Deploy static assets to Netlify/Vercel or GitHub Pages.  
3. ​Embed in Google Sites  
* Use “Embed → By URL” or iframe to include the chat UI on your existing MindCare Site.  
* ​Verify mobile behavior and cross‑origin issues (CORS, mixed content).

**Output:** real users can talk to MindCare via Google Sites, backed by your new stack.

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

## Phase 6 – Dedicated web app (dropping Google Sites)

1. Full web app  
* Build a Next.js or full React app with:  
  * Landing page (what MindCare is/isn’t, safety info).  
  * Chat page with better UI, avatar, conversation sections.  
  * Static pages: About, Data & Privacy, Resources.  
2. Optional accounts  
* If you ever add persistent user accounts, implement auth (e.g., passwordless email login or OAuth) and update schema to link sessions to users.  
* Re‑evaluate privacy/PHI risk before storing any contact info.  
3. Decommission Google Sites  
* Redirect visitors from the old Site to the new domain (or keep it as a simple pointer).

## Phase 7 – Evaluation and ethics

* Periodically review conversations (anonymized) against published mental‑health chatbot safety checklists and user‑experience studies, tweaking prompts and guardrails.  
  * Test against SAMHSA safe messaging guidelines.  
  * Evaluate at least one random sample of 20+ conversations for tone, safety compliance, and naturalness.  
  * Document any prompt changes and the rationale  
* Consider running small usability tests with friends/volunteers to get qualitative feedback on tone, clarity, and perceived safety.