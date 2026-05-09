# MindCare backend: chat routing and responses

This document describes how the **current** FastAPI backend handles `POST /api/v1/chat`: validation, pre-LLM rules, the Claude call, merging risk, templates, and the JSON returned to clients. It reflects the code as implemented today (regex pre-classification plus structured JSON from the model). A planned **dedicated safety classifier** is documented separately in `docs/LLM_SAFETY_ROUTER_PLAN.md` and is **not** part of the live pipeline yet.

**Scope:** Chat routing and responses only. Run/deploy instructions, dependency install, and the web app live elsewhere (e.g. `README.md`, `docs/DEV_COMMANDS.md`). There is no database layer in MVP; session state is in-process memory.

**Related:** `docs/API_CONTRACT.md` (response shape), `docs/SAFETY_POLICY.md` (policy intent), `mindcare/routers/chat.py`, `mindcare/llm.py`, `mindcare/schemas.py`, `mindcare/session_store.py`, `mindcare/rate_limiter.py`, `mindcare/config.py`.

---

## 1. Application entry

- **Framework:** FastAPI (`mindcare/main.py`).
- **Chat route:** `POST /api/v1/chat` → `chat()` in `mindcare/routers/chat.py`.
- **Prefix:** Router is mounted at `/api/v1`; health checks live at `/` and `/health`.

CORS allows origins from settings (`MINDCARE_CORS_ORIGINS`, default local dev ports).

---

## 2. Request and response (contract summary)

**Request** (`ChatRequest`): optional `session_id`, required `message`, optional `metadata`. The chat handler does **not** read `metadata` today (it is accepted for forward-compatible clients only).

**Response** (`ChatResponse`): `session_id`, `request_id`, `reply_text`, `risk_level` (`low` | `medium` | `high`), `policy_action`, `resources` (list of `ResourceItem`), optional `fallback_reason`, `latency_ms`.

`policy_action` values the handler actually uses today include: `normal`, `medium_llm`, `high_template`, `high_policy_template`, and `fallback` (e.g. LLM JSON parse failure → fixed medium template body). The schema also allows `medium_template` and `blocked` for forward compatibility; the current chat handler does not emit `medium_template` or `blocked`.

---

## 3. End-to-end order of operations

For each chat request the backend applies steps in this order:

1. **Normalize input** — Strip whitespace; reject empty messages (`400`).
2. **Length check** — Reject if over `max_message_length` (default 2000; `Settings.max_message_length`).
3. **Session** — Resolve or create `session_id` (`SessionStore`). History is in-memory, capped (default 10 turns → 20 messages; `max_session_turns` × 2), and **lost on process restart**. Clients may send any non-empty `session_id`; if it is new to this server process, an empty deque is created for that id.
4. **Rate limit** — In-memory **sliding window** (`mindcare/rate_limiter.py`). **Both** limits must pass: per `session_id` and per **SHA-256–hashed** client IP (from `Request.client.host`, or `"unknown"`). If either bucket is full → `429`. Defaults are 20 requests per 300 seconds; see `Settings.rate_limit_max_requests` and `rate_limit_window_seconds` in `mindcare/config.py` (and env overrides your deployment uses).
5. **Pre-LLM classification** — Regex-only `pre_risk` and optional keyword notes (see §4). No LLM yet.
6. **Debug log (optional)** — If `MINDCARE_CHAT_DEBUG=true`, log request-side trace at WARNING.
7. **Session lock** — If this session already has **≥3 high-risk turns** recorded, return the **crisis high template** immediately (`policy_action: high_template`, `trigger_source: session_lock`). No LLM call.
8. **Pre-LLM high paths** — If `pre_risk == "high"`, return a fixed template (see §5). No LLM call.
9. **LLM path** — Call `complete_chat_turn()` (Claude) with prior history and the current user message (see §6).
10. **Merge risk** — `final_risk = max(pre_risk, structured.risk_level)` using ordering low < medium < high.
11. **Post-LLM string check** — If the model’s `reply_text` matches disallowed patterns, replace with **high policy template** and discard model text (`policy_action: high_policy_template`, `fallback_reason: post_llm_disallowed_output`).
12. **Branch on `final_risk`** — High → crisis template (model reply discarded if LLM was used). Medium → keep model reply with disclaimer + resource list. Low → return model reply as-is; **`resources` is an empty list** on the normal path.
13. **Persist turn** — User and assistant messages are appended to session history when a template path uses `_template_response`, or when returning medium/low LLM replies (not when returning early `503`/`500`/`429` before a successful body is built).

High-risk **turn counter:** Incremented when the response path uses `_template_response` with `risk_level == "high"` (session lock, pre-LLM high, post-LLM overrides, and LLM-merge-to-high). It is **not** incremented for `medium_llm` or `normal` responses.

---

## 4. Pre-LLM classification (regex)

Implemented in `_pre_llm_classification()` in `chat.py`. Patterns are evaluated in a **fixed order**; the first matching category wins.

| Order | Category | Effect | `pre_high_kind` (if high) |
|-------|-----------|--------|---------------------------|
| 1 | **Injection** (`_INJECTION_PATTERNS`) | `pre_risk = high` | `policy` |
| 2 | **Harm-seeking how-to** (`_HARM_SEEKING_USER_PATTERNS`) | `pre_risk = high` | `policy` |
| 3 | **Crisis ideation** (`_HIGH_CRISIS_IDEATION_PATTERNS`) | `pre_risk = high` | `crisis` |
| 4 | **Word “overdose”** (standalone rule) | `pre_risk = high` | `crisis` |
| 5 | **Medium distress** (`_MEDIUM_PATTERNS`) | `pre_risk = medium` | — |
| 6 | (none) | `pre_risk = low` | — |

Keyword hits are collected in `pre_keyword_notes` for logging and, for medium, forwarded to the LLM as internal routing context (§6).

Matching is case-insensitive (`re.IGNORECASE`).

---

## 5. Fixed templates (no conversational LLM)

All template bodies are defined in `chat.py` and are **not** loaded from `docs/CRISIS_COPY.md` at runtime (copy may still be aligned with that doc editorially). Every template response appends the same **location disclaimer** paragraph (U.S. vs local emergency).

- **`high_template`** — Crisis / ideation path (`_HIGH_TEMPLATE_BODY`). Used for session lock, pre-LLM crisis matches, and when `final_risk == "high"` after the model (model reply is not shown).
- **`high_policy_template`** — Refusal / policy path (`_HIGH_POLICY_TEMPLATE_BODY`). Used for pre-LLM injection/harm-seeking matches and post-LLM disallowed output.
- **Medium fallback template** — `_MEDIUM_TEMPLATE_BODY` when the model returns **unparseable JSON** or schema-invalid payload (`policy_action: fallback`, `fallback_reason: llm_parse_failed`).

Template responses always include the standard **`resources`** list (988, Crisis Text Line, NAMI, 911).

---

## 6. LLM call (`complete_chat_turn`)

**Module:** `mindcare/llm.py`.

- **Provider:** Anthropic Messages API; API key from `ANTHROPIC_API_KEY` (missing → `RuntimeError`, surfaced as `503` to client).
- **Model / caps:** `ANTHROPIC_MODEL` (default in settings), `ANTHROPIC_MAX_TOKENS`.
- **System prompt:** `mindcare/prompts/system.txt` — instructs a single JSON object with `reply_text`, `risk_level`, `suggested_policy_action` (no markdown fences).
- **History:** Prior turns from `SessionStore.history_for_prompt` (user/assistant only). The **current** user message is always the last user turn.
- **Medium signals:** If `pre_risk == "medium"`, the handler passes `pre_keyword_notes` into the LLM as an **internal suffix** on the user message (`_MEDIUM_SIGNAL_PREFIX` … `]`). The user does not see this suffix; it nudges empathy and 988 per the system prompt.

**Parsing:** Response text is parsed as JSON; if that fails, optional extraction from a ```json fenced block. Failure → `ValueError` → handler returns medium template fallback (§5).

**Note:** `suggested_policy_action` from the model is logged in debug output but **routing** after a successful parse is driven by `structured.risk_level` merged with `pre_risk` and by post-LLM checks—not by blindly following `suggested_policy_action`.

---

## 7. Post-LLM reply text check

`_disallowed_pattern_hits()` scans **model `reply_text`** for patterns such as self-harm how-to, dosing, and “step-by-step”. Any hit → response is replaced with **`high_policy_template`**, model text discarded, `trigger_source: post_llm`.

---

## 8. Medium and low LLM outcomes

- **`final_risk == "medium"`** — Assistant text is the model’s `reply_text` with the **location disclaimer** appended. `policy_action` is **`medium_llm`**. **`resources`** are the same list as templates. `trigger_source` is `pre_llm` if regex already marked medium, else `llm`.
- **`final_risk == "low"`** — Assistant text is the model’s `reply_text` (no disclaimer added). `policy_action` is **`normal`**. **`resources` is `[]`**.

After a successful parse, the handler sets `reply = structured.reply_text.strip()`; if that is empty, it substitutes `Settings.empty_reply_fallback` (default short reassurance string) before post-LLM checks and persistence.

---

## 9. Errors and HTTP status codes

| Situation | Typical status |
|-----------|----------------|
| Empty / too-long message | `400` |
| App rate limit | `429` |
| Missing API key | `503` |
| Anthropic 401 / 403 / 404 / 400 / 529, connection issues | `503` (some cases with specific `detail` text) |
| Anthropic 429 | `429` |
| Unexpected handler bug | `500` |

Policy-driven fallbacks (e.g. bad model JSON) return **`200`** with `policy_action: fallback` and a safe template body, per MVP decisions in `docs/DECISIONS_LOG.md`.

---

## 10. Observability

- **Structured logs:** `logger.info` lines per outcome (`chat_policy_template`, `chat_policy_medium_llm`, `chat_policy_normal`) include `request_id`, `session_id`, `risk_level`, `policy_action`, `latency_ms`, etc.
- **Optional verbose trace:** `MINDCARE_CHAT_DEBUG=true` emits multiline `[chat-debug]` blocks at WARNING (request preview, pre-LLM risk, outcome path, merged risk, post-LLM hits). Avoid enabling in production if message previews in logs are unacceptable.

---

## 11. Planned changes (not implemented here)

When `docs/LLM_SAFETY_ROUTER_PLAN.md` is implemented, expect an optional **second LLM call** for classification, env flags such as `MINDCARE_USE_LLM_ROUTER`, a **`merged_pre_chat`** step, and stricter merge rules documented in `docs/SAFETY_POLICY.md`. This file should be updated at that time to match the code.

---

## 12. Revision history

| Date | Change |
|------|--------|
| 2026-05-09 | Initial document: current `/chat` routing and responses only. |
| 2026-05-09 | Scope note; metadata unused; session/rate-limit details; empty-reply fallback; related `rate_limiter` / `config`. |
