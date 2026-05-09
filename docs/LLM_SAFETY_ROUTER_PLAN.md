# Plan: LLM-assisted safety routing (MindCare)

This document describes how to add **AI-assisted classification** for nuanced safety routing while keeping **deterministic hard gates** for obvious harm-seeking and injection. It is a design and rollout plan only; implementation is tracked separately.

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
4. **Cost / latency budget** — At most **one extra LLM call per turn** when the router is enabled (classifier + existing reply call), unless a path short-circuits to templates with no LLM.
5. **Feature-flagged rollout** — Ship behind configuration (env / settings) so behavior can be compared and rolled back without rewriting core logic.

---

## 3. Proposed pipeline (high level)

```text
Request
  → validate / rate limit / session
  → [Hard gate A] injection + harm-seeking user text
        → high_policy_template (no classifier, no chat LLM)
  → [Hard gate B] unmistakable first-person crisis phrases
        → high_template (recommended default: **on**; see §7.1)
  → [Classifier LLM] if enabled and not short-circuited
        → JSON: risk_level, intent bucket, recommended_action, confidence (see §3.2)
        → optional short rationale: **logging only**, off by default in production (see §3.2)
  → Merge with any legacy pre-regex “medium” signals
        (or retire medium regex in favor of classifier — phased; see §5)
  → [Chat LLM] only if policy allows (e.g. normal / medium_llm paths)
  → Post-LLM safety (existing blocklist + template overrides)
  → Response
```

### 3.1 Routing inputs and merge authority (classifier vs chat-turn JSON)

Today the **chat completion** returns structured JSON (`LLMStructuredPayload`: `risk_level`, `suggested_policy_action`, etc.), and the handler merges that with **regex pre-classification** via a “take the higher risk” rule.

After the dedicated **classifier** exists, define a single merge story so implementers do not double-count or contradict each other:

1. **`merged_pre_chat`** — Combine **hard gates** (never downgraded by anything below), **classifier output** (when enabled and successful), and **legacy soft signals** (medium regex or classifier-only soft risk per Phase 3). Document the exact function in `docs/SAFETY_POLICY.md` and one implementation site (see Phase 2). Hard gates always win over the classifier and over soft regex for escalation.
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

### Phase 1 — Skeleton (default: no behavior change)

- Add settings flag, e.g. `MINDCARE_USE_LLM_ROUTER=false` (name TBD; document in `.env.example` and `README.md`).
- Optional: `MINDCARE_CLASSIFIER_MODEL` (and related max-tokens) — see §3.2; document in `.env.example`.
- Add `classify_safety_turn(...)` (e.g. in `mindcare/llm.py` or `mindcare/safety_classifier.py`):
  - Input: latest user message; optionally last *N* turns (see §7).
  - System prompt: strict JSON schema; no markdown fences.
  - Pydantic model: e.g. `SafetyClassificationPayload` (include `confidence` enum per §3.2; `rationale` optional and unused in prod by default).
- Integrate in `chat.py` **behind the flag**. When off, keep current `_pre_llm_classification` behavior unchanged.
- Logging: when flag on, log classifier outcome, confidence, and merge result per §3.2 (no extra PII beyond existing chat-debug practices).

### Phase 2 — Merge logic and fallbacks

- Document merge order in `docs/SAFETY_POLICY.md` and implement in one place (single function or small module):
  - Hard gates **cannot be downgraded** by the classifier (see §7).
  - On classifier parse failure, missing `confidence`, or `confidence == "low"` (§3.2): fall back to **current regex pre-classification** for soft routing (recommended) or a single safe default — pick one and document in `SAFETY_POLICY.md`.
- Session lock (3+ high-risk turns) must still **win** after merge.

### Phase 3 — Regex medium heuristics: narrow or replace

- **Option A (safer):** Keep medium regex only as **signals** fed into the classifier (similar to today’s `pre_medium_signals`) until evals are stable.
- **Option B (cleaner):** Classifier becomes the sole source of soft `pre_risk` for non-hard-gated messages; remove duplicate medium regex to avoid double-counting.

### Phase 4 — Evals and tests

- Extend `docs/TEST_PROMPT_CORPUS.json` with classifier-focused cases (third-party, negation, educational mentions, etc.).
- Tests:
  - **Mocked** classifier returning fixed JSON → assert merge and final `policy_action` / `risk_level`.
  - Optional: `@pytest.mark.integration` with real API key, **skipped in CI**.
- Manual: `docs/MANUAL_TEST_PROMPTS.md` + `scripts/sample_chat_responses.py` after prompt changes.

### Phase 5 — Rollout

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

1. **Hard crisis gate (gate B)** — **Default for v1: on** — Keep regex `high_template` for unmistakable first-person crisis phrases **without** calling the classifier (latency + certainty). Optional **off** only for experiments; document in `DECISIONS_LOG.md` if disabled anywhere long-lived.
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
