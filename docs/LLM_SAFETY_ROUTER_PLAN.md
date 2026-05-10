# Plan: LLM-assisted safety routing (MindCare)

This document describes **AI-assisted classification** for nuanced safety routing while keeping **deterministic hard gates** for obvious harm-seeking and injection. **Phases 1–4 are implemented** in `mindcare/routers/chat.py`, `mindcare/llm.py`, and `mindcare/safety_merge.py` behind **`MINDCARE_USE_LLM_ROUTER`** (see `docs/BACKEND_CHAT_ROUTING.md` for the live order of operations). Remaining work is mainly **Phase 5 rollout** (staging metrics, production enablement) and ongoing evals.

**Related docs:** `docs/SAFETY_POLICY.md`, `docs/BACKEND_CHAT_ROUTING.md` (current code path), `docs/API_CONTRACT.md`, `docs/CRISIS_COPY.md`, `docs/TEST_PROMPT_CORPUS.json`, `docs/MANUAL_TEST_PROMPTS.md`.

---

## 1. Goal

Reduce reliance on brittle regex for edge cases (third-party concern, negations, ambiguous wording) while preserving:

- Verbatim crisis / refusal templates where policy requires them.
- Fast, predictable handling for explicit harmful requests and jailbreak-style prompts.
- Existing post-LLM safeguards and session lock behavior.

The model’s primary job is **routing and classification**, not replacing fixed template copy where policy mandates it.

---

## 2. Non-negotiable principles

1. **Deterministic first** — Explicit harm-how-to, injection patterns, and any “must never reach the conversational LLM” cases remain **hard pre-checks**.
2. **Structured output only** — The classifier returns **validated JSON** (same pattern as `LLMStructuredPayload` today).
3. **Merge, don’t blindly trust** — Combine hard signals, classifier output, and legacy soft signals into `merged_pre_chat`, then apply **`final_risk = max(merged_pre_chat, reply_json.risk_level)`** (§3.1). Classifier **`confidence`** → **documented safe fallback** when low or missing (§3.2).
4. **Cost / latency budget** — With the router on: **at most one small-model (`classify_safety_turn`) call** per request on the main path, plus the **chat** completion when templates are not returned. Pre-LLM ambiguous crisis (`crisis_perspective`) uses the **same** classifier call—not a second router. Paths that return fixed templates skip the chat LLM (and may skip the merge-time classifier if pre-LLM high already returned).
5. **Feature-flagged rollout** — Ship behind configuration (env / settings) so behavior can be compared and rolled back without rewriting core logic.

---

## 3. Proposed pipeline (high level)

```text
Request
  → validate / rate limit / session
  → [Hard gate A] injection + harm-seeking user text
        → high_policy_template (no classifier, no chat LLM)
  → [Hard gate B] inherently first-person crisis grammar
        → high_template (no classifier, no chat LLM)
  → [Hard gate B′] ambiguous crisis keywords (e.g. suicide / overdose wording not clearly self vs other)
        → if MINDCARE_CRISIS_PERSPECTIVE_LLM: one classify_safety_turn → high_template vs high_supporter_template; else high_template
        → (no chat LLM)
  → [Classifier LLM] if MINDCARE_USE_LLM_ROUTER and not already returned above
        → JSON: risk_level, intent_bucket, recommended_action, confidence (§3.2)
        → merge_pre_chat_risk; if merged high → fixed templates (no chat LLM)
  → [Chat LLM] only if policy allows (normal / medium_llm paths)
  → Post-LLM safety (existing blocklist + template overrides)
  → Response
```

When **`MINDCARE_USE_LLM_ROUTER`** is true, legacy **`_MEDIUM_PATTERNS`** are not applied in pre-LLM classification; medium vs low for the chat path comes only from the classifier merge above.

### 3.1 Routing inputs and merge authority (classifier vs chat-turn JSON)

Today the **chat completion** returns structured JSON (`LLMStructuredPayload`: `risk_level`, `suggested_policy_action`, etc.), and the handler merges that with **regex pre-classification** via a “take the higher risk” rule.

After the dedicated **classifier** exists, define a single merge story so implementers do not double-count or contradict each other:

1. **`merged_pre_chat`** — Combine **hard gates** (never downgraded), **classifier output** when `MINDCARE_USE_LLM_ROUTER` is on and the classifier is trusted, and **legacy soft signals** when the router is off (**regex medium** still sets `pre_risk`). Exact merge: `mindcare/safety_merge.merge_pre_chat_risk`; policy narrative: `docs/SAFETY_POLICY.md` §4–§5. Hard gates always win for escalation.
2. **Chat-turn `risk_level` (reply JSON)** — Still produced by the conversational model. Use it as a **secondary safety check**, not as the primary router:  
   **`final_risk = max(merged_pre_chat, reply_json.risk_level)`** (same ordering as today: `low` < `medium` < `high`).  
   So the reply model **cannot downgrade** below what pre-chat routing already committed to (templates, skipped chat LLM, or stricter prompts). It can still **escalate** (e.g. surface crisis wording the classifier missed).
3. **`suggested_policy_action` from the reply JSON** — Keep subject to the same post-merge `final_risk` and existing post-LLM blocklist / template overrides; do not let it bypass hard gates or session lock.

### 3.2 Classifier `confidence` and logging (v1)

**`confidence` (required in schema; see fallback if missing):** Use a **string enum** only in v1 — e.g. `"high" | "medium" | "low"` — meaning the model’s **self-reported certainty** in its `risk_level` / `recommended_action`, not a calibrated probability. Do **not** rely on logprobs or numeric thresholds until a later version documents calibration.

- If `confidence` is **`low`**, or the classifier JSON **fails validation**, apply the Phase 2 **documented fallback** (recommended: legacy regex pre-classification for **soft** routing only; hard gates unchanged).
- If the field is **missing** after a partial parse, treat as **`low`** and use the same fallback.

**Optional `rationale`:** Never required for routing correctness; **omit from production logs by default** (settings flag, off in prod). When enabled (e.g. staging), apply the same **truncation / redaction** practices as existing chat-debug logs so user content is not duplicated verbatim in long free-text fields. Never return rationale to clients in v1.

**Classifier model:** Prefer an optional **separate model id** (e.g. `MINDCARE_CLASSIFIER_MODEL`) so production can use a **smaller / faster / cheaper** completion for the router call while keeping the main chat model for replies. If unset, default to the existing chat model to reduce configuration burden in dev.

---

## 4. Implementation phases

### Phase 1 — Skeleton (**done**)

- Settings: `MINDCARE_USE_LLM_ROUTER`, `MINDCARE_CLASSIFIER_MODEL`, `MINDCARE_CLASSIFIER_MAX_TOKENS`, `MINDCARE_CLASSIFIER_LOG_RATIONALE` (see `.env.example`).
- `classify_safety_turn` in `mindcare/llm.py`; payload `SafetyClassificationPayload` in `mindcare/schemas.py`; prompt `mindcare/prompts/classifier_system.txt`.

### Phase 2 — Merge logic and fallbacks (**done**)

- `merge_pre_chat_risk` in `mindcare/safety_merge.py`; documented in `docs/SAFETY_POLICY.md`.
- Session lock unchanged.

### Phase 3 — Regex medium vs classifier (**done; hybrid**)

- **Router off:** Legacy **`_MEDIUM_PATTERNS`** still set `pre_risk = medium`; trusted merge uses Phase 3 **baseline** so regex-only medium does not force the classifier above `low` when the model returns trusted `low`.
- **Router on:** **`_MEDIUM_PATTERNS` are not evaluated** in `_pre_llm_classification`; medium vs low is **classifier-only** (same `classify_safety_turn` call as merge). **Soft empathy** when merge is `low` uses **`intent_bucket`** in `{distress, ambiguous_distress, hopelessness}` instead of regex hits (`MINDCARE_SOFT_EMPATHY_HINTS`).

### Phase 4 — Evals and tests (**done**)

- `docs/TEST_PROMPT_CORPUS.json` v0.3+ with `class_*` cases; `tests/test_phase4_classifier_routing.py`; opt-in `tests/test_integration_chat.py`; `scripts/sample_chat_responses.py --include-phase4-corpus`.

### Phase 5 — Rollout (**ongoing**)

- Enable flag in staging; review logs: distribution of `policy_action`, false positives/negatives vs baseline.
- Production enable only after latency, error rate, and cost checks pass.

---

## 5. Success criteria

- Third-party and ambiguous prompts route **more consistently** without growing regex indefinitely.
- Corpus + manual matrix: **no regression** on hard paths; no harmful how-to in replies.
- With flag on: acceptable **latency (e.g. p95)** and **cost**; flag off restores prior behavior.

---

## 6. Documentation touchpoints (when implementing)

| Artifact | Purpose |
|----------|---------|
| `docs/SAFETY_POLICY.md` | Classifier role, merge order, failure behavior |
| `docs/DECISIONS_LOG.md` | Record flag default, merge policy, any scope change |
| `.env.example` | Router flag, optional classifier model id / max tokens (§3.2) |
| `README.md` | Short pointer to flag and this plan |
| `docs/API_CONTRACT.md` | Update only if new **client-visible** fields are added (prefer avoiding for MVP) |

---

## 7. Open decisions (resolve before or during Phase 2)

1. **Hard crisis gate (gate B)** — **Default for v1: on** — Inherently first-person self-harm grammar (`kill myself`, etc.) returns **`high_template`** **without** the classifier. **Ambiguous** crisis keywords (e.g. bare `suicide`, `want to die` without clear self vs other) use **one** `classify_safety_turn` when `MINDCARE_CRISIS_PERSPECTIVE_LLM` is enabled to choose **`high_template`** vs **`high_supporter_template`**; if disabled or on failure, default to first-person template.
2. **Classifier input** — **Message-only** vs last *k* turns. Message-only is simpler and cheaper; history helps disambiguate “my friend…” vs “I…” but increases tokens and logging sensitivity.
3. **Downgrade rule** — Can the classifier lower risk below a **soft** regex hit (e.g. medium heuristic)? Recommend: **only** where policy explicitly allows (e.g. third-party routing); **never** below hard gates. (Does not apply to **`merged_pre_chat` vs reply JSON**: reply JSON may only escalate; see §3.1.)
4. **Second-call cost** — Two LLM calls on many turns (classifier + reply). Mitigations: skip classifier when a hard gate already fired; use optional smaller classifier model (§3.2); defer “session stability” optimizations until v2.

---

## 8. Out of scope (initial version)

- Training a separate small model on your infra.
- Returning detailed classifier rationale to end users.
- Persisting classifier outputs beyond existing ephemeral session / logs (unless product later requires it).

---

## 9. Revision history

| Date | Change |
|------|--------|
| 2026-05-09 | Initial plan authored for post-commit implementation. |
| 2026-05-09 | Filled gaps: merge authority vs chat JSON (§3.1), confidence + logging + classifier model (§3.2), gate B default, Phase 1 / §7 touch-ups. |
| 2026-05-09 | Phase 3 **Option A** implemented: medium regex as classifier/chat hints only under `MINDCARE_USE_LLM_ROUTER`; trusted merge baseline strips regex-only medium (`mindcare/safety_merge.py`). |
| 2026-05-09 | Phase 4: corpus v0.2 (`class_*` cases), `test_phase4_classifier_routing.py`, opt-in `test_integration_chat.py`, sample script `--include-phase4-corpus`. |
| 2026-05-09 | **Superseded Phase 3 (router on):** legacy medium regex **skipped** when `MINDCARE_USE_LLM_ROUTER`; classifier-only soft tier; `high_supporter_template` + single `classify_safety_turn` for ambiguous crisis keywords; soft empathy via `intent_bucket`. Corpus **v0.3** notes; `docs/SAFETY_POLICY.md` / `BACKEND_CHAT_ROUTING.md` updated. |
