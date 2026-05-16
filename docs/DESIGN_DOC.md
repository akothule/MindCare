# MindCare Design Document (v0.2)

*v0.2 — Aligns MVP safety architecture with the optional **LLM safety router** (`MINDCARE_USE_LLM_ROUTER`): dedicated `classify_safety_turn`, merge pre-chat risk, **`high_supporter_template`** for third-party crisis wording, and router-on behavior where legacy medium phrase regex is disabled in favor of the classifier (see `docs/SAFETY_POLICY.md` §4, `docs/BACKEND_CHAT_ROUTING.md`).*

## 1\. Purpose and goals

**Problem:** Many people need low‑barrier, stigma‑free emotional support, but access to human support is limited by cost, availability, and timing (especially nights and weekends).

**MindCare’s Role:**

* Provide a 24/7, conversational, AI‑driven companion that helps users reflect on their feelings and learn basic coping strategies.  
* Encourage connection to real people and professional help when needed, not replace them.

**Primary goals (MVP):**

* Offer warm, validating, human‑like conversations around day‑to‑day emotional struggles.  
* Gently suggest evidence‑informed self‑help strategies (grounding, journaling prompts, behavioral activation) without acting as a therapist.  
* Detect signs of self‑harm/suicidal ideation and respond with safe, pre‑approved crisis guidance and resources.  
  * Risk detection uses **layers**: deterministic keyword / phrase **hard gates** (injection, harm-how-to, crisis stems) where policy requires templates without the conversational LLM; an optional **safety classifier** completion (`classify_safety_turn`, same provider) when `MINDCARE_USE_LLM_ROUTER` is enabled merges nuance (medium vs low, third-party vs self for ambiguous crisis text); the **chat** completion still returns structured JSON whose `risk_level` is merged as a secondary check (`final_risk = max(merged_pre_chat, reply_json.risk_level)`).

**Non‑goals (what MindCare will NOT do):**

* Diagnose any mental health condition.  
* Give medication or treatment instructions.  
* Provide emergency intervention or guarantee contact with a human professional.

## 2\. Target users and usage scenarios

**Target users:**

* Global users (all ages) who want anonymous emotional support and psychoeducation.
* People who are hesitant to see a therapist or are on waitlists and want “someone to talk to” right now.

**Example use cases:**

* “I’m really anxious about school and can’t sleep.”  
* “I feel lonely and like no one understands me.”  
* “I’m happy something good happened and I want to share it.”  
* “I’m having thoughts about hurting myself.”

## 3\. High‑level system overview

**Architecture (MVP):**

* Frontend:  
  * **MVP UI** is a small SPA in-repo under **`web/`** (Vite + React + TypeScript), implemented for local use and static builds; production deployment targets a static host (primary plan: **Vercel**). Equivalent hosts include Netlify, Cloudflare Pages, or GitHub Pages. You can still embed that URL in another page (e.g. iframe) if needed; the API contract stays the same.  
  * A fuller multi-page app can come later (Phase 6); the same `/api/v1/chat` contract still applies.  
* Backend (core):  
  * Python/FastAPI REST API with main endpoint /api/v1/chat.  
  * Integrates with an LLM provider to generate responses.  
  * Implements safety checks and logging around each interaction.  
* Data storage:  
  * Out of MVP scope; start with ephemeral session memory only.  
* External services:  
  * LLM API (Claude for MVP).
  * Optional monitoring/logging service later.

### Architecture diagram (MVP)

The diagrams below use **Vercel** for the frontend and **Render** for the API. **Netlify, GitHub Pages, Cloudflare Pages**, or another static/SPA host are equivalent to Vercel for the UI.

**MVP scope called out in the diagrams:** **No user authentication** (anonymous `session_id` only), **no persistent database** (in-process memory only), **no separate Redis** unless you add it later. **Secrets** live in Render (and optional non-secret env on Vercel for public config like API base URL). **DNS and TLS** are provided by Vercel and Render; **CDN/edge** is implicit on Vercel for static assets.

#### Figure 1 — Deployment and major components

Shows *where* things run and *what* talks to what. The FastAPI service may call Anthropic **twice per chat turn** when the safety router is on (one smaller **classifier** completion if configured, plus the **chat** completion), or once when the router is off—unless a template path short-circuits before the chat call.

```mermaid
flowchart TB
  U[User]
  BR[Browser]
  subgraph vercel["Vercel"]
    EDGE[Vercel Edge / CDN]
    UI[Chat UI - static or SPA]
  end
  subgraph render["Render"]
    subgraph secrets["Config"]
      ENV[Environment secrets — Anthropic key, model id]
    end
    subgraph fastapi["FastAPI service"]
      MW[Middleware: CORS + rate limit]
      CORE[Chat handler + safety pipeline]
      MEM[(In-memory sessions - last N turns)]
      LOG[Structured logs]
    end
  end
  subgraph external["Third-party APIs"]
    ANTH[Anthropic Claude API]
  end
  U --> BR
  BR -->|GET page, HTTPS| EDGE
  EDGE --> UI
  UI -->|POST /api/v1/chat JSON, HTTPS| MW
  ENV -.->|read at runtime| CORE
  MW --> CORE
  CORE <--> MEM
  CORE --> LOG
  CORE -->|HTTPS, API key from env| ANTH
```

**Post-MVP (dashed idea, not required now):** external **metrics/APM** (e.g. hosted logging), **managed DB** for sessions or audit logs, **Redis** for shared session if you scale beyond one instance.

#### Figure 2 — Logical request path inside the API

Matches the pipeline in `docs/SAFETY_POLICY.md` §4 and the step list in `docs/BACKEND_CHAT_ROUTING.md` §3. Hard gates and many **high** paths use fixed templates **without** the conversational LLM. When **`MINDCARE_USE_LLM_ROUTER`** is on, a **classifier** call may run before merge; it does **not** replace hard gates.

```mermaid
flowchart TB
  IN[Incoming POST /api/v1/chat]
  V[1 - Validate + normalize input]
  R[2 - Pre-LLM: hard gates + regex medium if router off]
  C[3 - classify_safety_turn + merge when router on]
  S[(4 - Load / update session context)]
  G{5 - Policy allows chat LLM?}
  L[6 - Chat completion - structured JSON]
  P[7 - Parse + validate JSON schema]
  F[8 - Post-LLM safety filters]
  POL[9 - Final policy override + template selection]
  OUT[10 - Response + structured logging]
  TPL[Fixed templates - CRISIS_COPY.md]
  IN --> V --> R
  R -->|router on| C
  R -->|router off| S
  C --> S
  S --> G
  G -->|yes, low / medium path| L
  G -->|template path high or merge high| TPL
  L --> P --> F --> POL
  TPL --> POL
  POL --> OUT
```

**Why omit auth, DB, and Redis from the boxes?** For MVP they are intentionally absent: sessions are **ephemeral** and **per server process** (`docs/DECISIONS_LOG.md`). Adding **Clerk/Auth0** or **Postgres** would be new components and belong in a post-MVP diagram.

**Request path (reference):** full policy detail is in `docs/SAFETY_POLICY.md`; API fields are in `docs/API_CONTRACT.md`.

## 4\. Functional requirements (MVP)

**FR‑1: Chatting**

* User can send a free‑text message and receive a response within N seconds (target: ≤ 8 s).  
* System preserves the last N turns of conversation context per session (e.g., last 8–10 messages).

**FR‑2: Session handling**

* System assigns a session\_id for each new visitor.  
* System keeps short in-memory chat context for response quality during the active session.

**FR‑3: Emotional support behavior**

* Each non‑crisis reply should:  
  * Acknowledge and validate the user’s feelings.  
  * Briefly reflect what the user said (paraphrase).  
  * Offer either a gentle question or a concrete coping suggestion (e.g., grounding exercise, small action).

**FR‑4: Crisis detection and response**

* System identifies messages suggesting self‑harm/suicide or harm using **regex hard gates** and, when **`MINDCARE_USE_LLM_ROUTER`** is enabled, a **validated JSON safety classifier** (`classify_safety_turn`) merged per `docs/SAFETY_POLICY.md`.  
* On **high** risk:  
  * Returns fixed, pre‑approved copy from `docs/CRISIS_COPY.md` — **first-person** crisis (**§1**, `high_template`), **supporter / third-party** concern (**§1a**, `high_supporter_template`), or **policy / refusal** (**§1b**, `high_policy_template`) as applicable.  
  * Does **not** use the conversational LLM for those template paths.  
  * Does NOT engage in speculative discussion (e.g., “Is life worth living?” replies must be very carefully constrained).  
* On **medium** risk:  
  * Encourages reaching out to trusted people and professional help, with resources (e.g. 988, Crisis Text Line, NAMI) when the merged path is **`medium_llm`**. With the router **on**, medium vs low is primarily **classifier-driven** (legacy phrase regex for medium is disabled in pre-LLM classification).

**FR‑5: Content limitations**

* System must refuse to:  
  * Give diagnostic labels (e.g., “You have depression”).  
  * Provide medication dosages or changes.  
  * Provide instructions for self‑harm or harming others.

**FR-6: Rate limiting and abuse prevention**

* Add a basic rate-limit requirement (e.g., max N messages per session per minute)

**FR-7: Disclaimers and onboarding**

* Show a disclaimer to the user.

## 5\. Non‑functional requirements

**NFR‑1: Safety and ethics**

* Align with mental‑health chatbot safety guidelines (APA and recent research): clear disclaimers, no impersonation of human clinicians, and consistent crisis procedures.

**NFR‑2: Privacy**

* No collection of real names, email, phone, or exact location in the MVP.  
* IP addresses only stored if absolutely needed for security/abuse prevention and not linked to content where possible.  
* Since conversation storage is out of MVP scope, data handling remains ephemeral for initial release.

**NFR‑3: Performance**

* 95th percentile response latency under 8 seconds at MVP load.  
* Degradation strategy if LLM is slow/unavailable (e.g., “I’m having trouble responding right now, please try again soon.”).

**NFR‑4: Reliability**

* /health endpoint indicates backend and LLM connectivity.  
* Logs allow tracing each request/response pair with session and risk level.

## 6\. Safety model and policies

**Risk levels:**

* Low: Everyday stress, mild sadness/anxiety, neutral or positive content.  
* Medium: Expressions of hopelessness or distress without explicit self‑harm intent. (“I don’t see the point of anything.”)  
* High: Explicit self‑harm/suicide ideation or plan, or threats to others.

**Policy rules (simplified):**

* For low risk messages: use standard supportive prompt, free‑flow conversation allowed within constraints.  
* For medium risk:  
  * Increase empathy and validation.  
  * Always recommend talking to a trusted person and/or professional.  
  * Provide relevant resources (e.g., NAMI, 988 in the U.S., Crisis Text Line).  
* For high risk:  
  * Return a fixed template (no improvisation from the **chat** LLM): first-person crisis, supporter/third-party crisis, or policy/refusal, per `docs/CRISIS_COPY.md` and `policy_action`.  
  * Emphasize contacting emergency services or crisis hotlines; clarify MindCare cannot provide emergency help.

**LLM usage policy:**

* All LLM calls use a strict system prompt with:  
  * Role and limitations.  
  * Safety instructions.  
  * Required JSON output schema (e.g., reply\_text, risk\_level\_suggested, style\_flags).  
* Post‑processing filters check for banned content and can override the response.

## 7\. Technology choices

**Backend:**

* Python 3.x, FastAPI, Uvicorn.  
* Async HTTP client (httpx) for LLM calls.  
* SQLAlchemy or another ORM for DB access (post-MVP when persistence is introduced).

**Database:**

* Post-MVP: managed Postgres (Supabase/Neon/etc.) for structured logs and sessions.

**Frontend (initial):**

* Simple React or vanilla JS chat widget hosted on Netlify/Vercel/GitHub Pages/Cloudflare Pages (or another static host).

**LLM provider:**

* Claude (Anthropic), provided use remains aligned with provider policy for mental-health-adjacent support. Must support:  
  * System prompts,  
  * JSON‑formatted output,  
  * Policy for mental‑health–adjacent use.

## 8\. Data model (conceptual, post-MVP)

**Session:**

* id (UUID)  
* created\_at, last\_active\_at  
* client\_metadata (user agent, locale, approximate region)

**Message:**

* id (UUID)  
* session\_id  
* role (user/assistant)  
* text  
* risk\_level (low/medium/high)  
* created\_at

Note: Session/message tables are conceptual and can be introduced post-MVP when persistence is implemented.

**Event (optional, later):**

* id, session\_id, type (e.g., feedback\_helpful, feedback\_unhelpful, high\_risk\_triggered)  
* metadata JSON

## 9\. Open questions and risks

* **Jurisdiction and compliance:** If usage grows beyond friends/testing, do we need HIPAA‑level controls or other regulatory review?  
* **Age strategy:** MVP uses a single safety policy for all users. Revisit youth-specific guidance/resources in later phases.
* **Abuse and misuse:** How do we handle users who try to game the system, prompt‑inject the LLM, or seek harmful content?  
* **Scaling:** At what point do we need more robust monitoring, rate‑limiting, and cost controls for LLM usage?  
* **LLM:** Claude selected for MVP; continue periodic checks against provider terms for mental-health-adjacent use.
* **Language translation:** How do we handle multilingual users?