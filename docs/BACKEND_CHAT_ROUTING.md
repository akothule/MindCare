# MindCare backend: chat routing and responses

This document describes how the **current** FastAPI backend handles `POST /api/v1/chat`: validation, pre-LLM rules, optional **safety classifier** (`classify_safety_turn`), the conversational Claude call, merging risk, templates, and the JSON returned to clients. When **`MINDCARE_USE_LLM_ROUTER`** is **false** (default in tests), routing uses **regex pre-classification** plus structured JSON from the chat model. When the flag is **true**, a **single classifier completion** (typically Haiku via `MINDCARE_CLASSIFIER_MODEL`) runs before the chat LLM for pre-chat merge, ambiguous high-template choice, and (with regex medium disabled) medium vs low. Design history: `docs/LLM_SAFETY_ROUTER_PLAN.md`.

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

`policy_action` values the handler actually uses today include: `normal`, `medium_llm`, `high_template`, `high_supporter_template`, `high_policy_template`, and `fallback` (e.g. LLM JSON parse failure → fixed medium template body). The schema also allows `medium_template` and `blocked` for forward compatibility; the current chat handler does not emit `medium_template` or `blocked`.

---

## 3. End-to-end order of operations

For each chat request the backend applies steps in this order:

1. **Normalize input** — Strip whitespace; reject empty messages (`400`).
2. **Length check** — Reject if over `max_message_length` (default 2000; `Settings.max_message_length`).
3. **Session** — Resolve or create `session_id` (`SessionStore`). History is in-memory, capped (default 10 turns → 20 messages; `max_session_turns` × 2), and **lost on process restart**. Clients may send any non-empty `session_id`; if it is new to this server process, an empty deque is created for that id.
4. **Rate limit** — In-memory **sliding window** (`mindcare/rate_limiter.py`). **Both** limits must pass: per `session_id` and per **SHA-256–hashed** client IP (from `Request.client.host`, or `"unknown"`). If either bucket is full → `429`. Defaults are 20 requests per 300 seconds; see `Settings.rate_limit_max_requests` and `rate_limit_window_seconds` in `mindcare/config.py` (and env overrides your deployment uses).
5. **Pre-LLM classification** — Regex `pre_risk` and keyword notes (see §4). With **`MINDCARE_USE_LLM_ROUTER`**, legacy **medium** phrase regex is **not** applied (`pre_risk` is `low` or `high` only). No LLM yet (except step 8b below).
6. **Debug log (optional)** — If `MINDCARE_CHAT_DEBUG=true`, log request-side trace at WARNING.
7. **Session lock** — If this session already has **≥3 high-risk turns** recorded, return the **crisis high template** immediately (`policy_action: high_template`, `trigger_source: session_lock`). No LLM call.
8. **Pre-LLM high paths** — If `pre_risk == "high"`, return a fixed template (see §5): **policy** → `high_policy_template`; **inherently first-person crisis** grammar → `high_template`; **ambiguous crisis keywords** (`crisis_perspective`) → one call to **`classify_safety_turn`** (same Haiku as the router) to choose **`high_template`** vs **`high_supporter_template`** when `MINDCARE_CRISIS_PERSPECTIVE_LLM` is enabled and API key present; otherwise default to first-person template. No chat LLM.
9. **Safety classifier + merge** (when **`MINDCARE_USE_LLM_ROUTER`** and step 8 did not return) — `classify_safety_turn()` then **`merge_pre_chat_risk()`** (`mindcare/safety_merge.py`). If **`merged_pre_chat == "high"`**, return the appropriate fixed high template (policy / supporter / crisis per classifier `recommended_action`); **no chat LLM**.
10. **Chat LLM** — `complete_chat_turn()` (Claude, `ANTHROPIC_MODEL`) with history, optional internal **medium signals** (`merge.medium_signal_notes`), and optional **soft empathy** calibration (`intent_bucket`–driven when merge is low; see §6).
11. **Merge reply risk** — `final_risk = max(merged_pre_chat, structured.risk_level)` using ordering low < medium < high (`merged_pre_chat` from step 9; `structured` from step 10).
12. **Post-LLM string check** — If the model’s `reply_text` matches disallowed patterns, replace with **high policy template** and discard model text (`policy_action: high_policy_template`, `fallback_reason: post_llm_disallowed_output`).
13. **Branch on `final_risk`** — High → fixed templates (model reply discarded if step 10 ran). Medium → keep model reply with disclaimer + resource list. Low → return model reply; disclaimer only when soft paths add it; **`resources` is `[]`** on the normal low path.
14. **Persist turn** — User and assistant messages are appended to session history when a template path uses `_template_response`, or when returning medium/low LLM replies (not when returning early `503`/`500`/`429` before a successful body is built).

High-risk **turn counter:** Incremented when the response path uses `_template_response` with `risk_level == "high"` (session lock, pre-LLM high, classifier-merge high, post-LLM overrides, and LLM-merge-to-high). It is **not** incremented for `medium_llm` or `normal` responses.

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

When **`MINDCARE_USE_LLM_ROUTER` is true**, step 5 is **skipped**: legacy medium phrase regex does not set `pre_risk`; medium vs low is decided only by **`classify_safety_turn`** (one Haiku with the main safety classifier). `pre_keyword_notes` then has no `medium_keyword:*` entries from this list. If the classifier merges **low** but `intent_bucket` is `distress`, `ambiguous_distress`, or `hopelessness`, the handler may still pass **soft empathy** hints to the chat model (no extra API call).

When the router is **off**, step 5 applies as above.

Keyword hits are collected in `pre_keyword_notes` for logging and, when `pre_risk == "medium"` (router off), forwarded to the classifier as `pre_medium_signals` and into the chat LLM as internal routing context (§6).

Matching is case-insensitive (`re.IGNORECASE`).

---

## 5. Fixed templates (no conversational LLM)

All template bodies are defined in `chat.py` and are **not** loaded from `docs/CRISIS_COPY.md` at runtime (copy may still be aligned with that doc editorially). Every template response appends the same **location disclaimer** paragraph (U.S. vs local emergency).

- **`high_template`** — First-person crisis / ideation path (`_HIGH_TEMPLATE_BODY`). Used for session lock, pre-LLM crisis matches that are not classified as third-party concern, classifier crisis high, and when `final_risk == "high"` after the model when supporter heuristics do not apply (model reply is not shown).
- **`high_supporter_template`** — Third-party / “worried about someone else” path (`_HIGH_SUPPORTER_TEMPLATE_BODY`). Used for pre-LLM high after the safety classifier chooses supporter on ambiguous crisis keywords, classifier `high_supporter_template`, and post-LLM high when the merged/classifier path indicates supporter.
- **`high_policy_template`** — Refusal / policy path (`_HIGH_POLICY_TEMPLATE_BODY`). Used for pre-LLM injection/harm-seeking matches and post-LLM disallowed output.
- **Medium fallback template** — `_MEDIUM_TEMPLATE_BODY` when the model returns **unparseable JSON** or schema-invalid payload (`policy_action: fallback`, `fallback_reason: llm_parse_failed`).

Template responses always include the standard **`resources`** list (988, Crisis Text Line, NAMI, 911).

---

## 6. LLM calls (`classify_safety_turn` + `complete_chat_turn`)

**Modules:** `mindcare/llm.py`, `mindcare/routers/chat.py`.

### 6a. Safety classifier (`classify_safety_turn`)

- Runs when **`MINDCARE_USE_LLM_ROUTER`** is true and the handler has not already returned. **At most one** `classify_safety_turn` per request: either inside **pre-LLM high** (`crisis_perspective`: ambiguous crisis keywords → §1 vs §1a) **or** on the **LLM-eligible path** for merge—never both.
- **Model:** `MINDCARE_CLASSIFIER_MODEL` if set, else `ANTHROPIC_MODEL`.
- **Prompt:** `mindcare/prompts/classifier_system.txt` — JSON with `risk_level`, `intent_bucket`, `recommended_action`, `confidence`, optional `rationale`.
- **Output:** Pydantic `SafetyClassificationPayload`; merged via `merge_pre_chat_risk` (see `docs/SAFETY_POLICY.md` §4).

### 6b. Conversational chat (`complete_chat_turn`)

- **Provider:** Anthropic Messages API; API key from `ANTHROPIC_API_KEY` (missing → `RuntimeError`, surfaced as `503` to client).
- **Model / caps:** `ANTHROPIC_MODEL` (default in settings), `ANTHROPIC_MAX_TOKENS`.
- **System prompt:** `mindcare/prompts/system.txt` — instructs a single JSON object with `reply_text`, `risk_level`, `suggested_policy_action` (no markdown fences).
- **History:** Prior turns from `SessionStore.history_for_prompt` (user/assistant only). The **current** user message is always the last user turn.
- **Medium signals:** If `merge.medium_signal_notes` is non-empty (e.g. regex `medium_keyword:*` when router off, or `classifier_intent:*` when merged risk is medium), the handler passes them into the LLM as an **internal suffix** on the user message (`_MEDIUM_SIGNAL_PREFIX` … `]`). The user does not see this suffix; it nudges empathy and 988 per the system prompt. **Soft empathy** (merged low, router on): optional short hints from classifier `intent_bucket` without promoting to medium (`apply_soft_empathy_calibration` in `llm.py`).

**Parsing:** Response text is parsed as JSON; if that fails, optional extraction from a ```json fenced block. Failure → `ValueError` → handler returns medium template fallback (§5).

**Note:** `suggested_policy_action` from the chat model is logged in debug output but **routing** after a successful parse uses **`final_risk = max(merged_pre_chat, structured.risk_level)`** and post-LLM checks—not by blindly following `suggested_policy_action`.

---

## 7. Post-LLM reply text check

`_disallowed_pattern_hits()` scans **model `reply_text`** for patterns such as self-harm how-to, dosing, and “step-by-step”. Any hit → response is replaced with **`high_policy_template`**, model text discarded, `trigger_source: post_llm`.

---

## 8. Medium and low LLM outcomes

- **`final_risk == "medium"`** — Assistant text is the model’s `reply_text` with the **location disclaimer** appended. `policy_action` is **`medium_llm`**. **`resources`** are the same list as templates. `trigger_source` is **`pre_llm`** if regex-only medium (`MINDCARE_USE_LLM_ROUTER` false) matched, **`classifier`** if merge medium came from the classifier (router on), else **`llm`** if elevation came mainly from reply JSON.
- **`final_risk == "low"`** — Assistant text is the model’s `reply_text` (no location disclaimer appended on the default normal path). `policy_action` is **`normal`**. **`resources` is `[]`**. Soft-empathy hints, when used, are **internal** text appended only for the model call (`apply_soft_empathy_calibration` in `llm.py`), not shown verbatim to the client.

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

## 11. Future / out of band

- **Client-visible classifier fields:** Not in MVP JSON; keep routing server-side unless `docs/API_CONTRACT.md` is intentionally extended.
- **Further regex retirement:** Hard gates (injection, harm-how-to, crisis stems) remain regex-first by policy unless a future version moves more into the classifier with eval gates.

---

## 12. Revision history

| Date | Change |
|------|--------|
| 2026-05-09 | Initial document: current `/chat` routing and responses only. |
| 2026-05-09 | Scope note; metadata unused; session/rate-limit details; empty-reply fallback; related `rate_limiter` / `config`. |
| 2026-05-09 | Documented live **`MINDCARE_USE_LLM_ROUTER`** path: `classify_safety_turn`, `merge_pre_chat_risk`, skip regex medium when router on, `crisis_perspective` + §6 split, `high_supporter_template`, revised steps 5–14 and §8 `trigger_source`. |
