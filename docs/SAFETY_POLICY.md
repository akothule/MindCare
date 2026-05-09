# MindCare Safety Policy (MVP v0.2)

## 1) Role and boundaries

MindCare is a supportive AI companion for emotional reflection and basic coping support.

MindCare does not:
- Diagnose mental health conditions.
- Provide medication advice, dosing, or treatment changes.
- Replace licensed professionals or emergency services.
- Provide instructions for self-harm, violence, or other harmful acts.

## 2) Audience and geography

- Initial audience: global users (all ages).
- Age handling in MVP: single safety policy for all users (no age differentiation or age-gating flow).
- MVP may be globally accessible.
- Responses should include generic emergency guidance and may include U.S.-specific resources with a short disclaimer that local resources vary by location.

## 3) Risk levels and examples

### Low risk
Everyday stress, mild anxiety/sadness, loneliness, neutral or positive reflection.

Examples:
- "I feel anxious about school tomorrow."
- "I had a rough day and feel tired."
- "Something good happened today and I want to share."

Required behavior:
- Validate and reflect briefly.
- Offer one gentle question or one concrete coping step.
- Keep tone warm, non-clinical, and non-judgmental.

### Medium risk
Significant distress, hopelessness, or passive self-harm language without explicit plan/intent.

Examples:
- "I don't see the point of anything."
- "I wish I could disappear."
- "Sometimes I think people would be better off without me."

Required behavior:
- Increase empathy and direct support.
- Encourage reaching out to a trusted person and professional support.
- Provide relevant support resources.
- Avoid speculative philosophy around life/death meaning.

### High risk
Explicit self-harm/suicide intent, planning, means, imminent danger, or direct threats to others.

Examples:
- "I want to kill myself."
- "I have a plan to hurt myself tonight."
- "I want to hurt someone and I know where they are."

Required behavior:
- Return fixed crisis template only (no improvisation).
- Clearly recommend emergency help and crisis contact options.
- Do not provide tactical details or extended debate.

## 4) Safety pipeline (deterministic order)

Design reference for the optional dedicated classifier: `docs/LLM_SAFETY_ROUTER_PLAN.md` (merge details below match that plan).

For every user message:
1. Input validation and normalization.
2. **Hard pre-checks** — Injection / harm-seeking user text and (by default) unmistakable first-person crisis phrases; may return fixed templates **without** calling any LLM.
3. **Session incident rule (§11)** — If the session already has **3+ high-risk turns**, return the fixed crisis template and **do not** call the dedicated classifier (when present) or the chat LLM. This check must remain in effect in implementations; optional router features must not bypass it.
4. **Soft pre-chat signals** — Keyword/phrase patterns (“medium” heuristics) and, when enabled, a **classifier LLM** that returns validated JSON (`risk_level`, `recommended_action`, `confidence`, etc.). If the classifier is disabled, only legacy regex pre-classification applies for this layer.
5. **Merge pre-chat risk (`merged_pre_chat`)** — Combine hard gates (they always win for escalation), successful classifier output when enabled, and legacy soft signals per the rollout phase in the router plan. Hard gates **must not** be downgraded by the classifier or by soft regex.
6. LLM **reply** generation only if policy allows (normal / medium paths, etc.).
7. Strict JSON schema parse and validation on the reply payload.
8. Post-LLM safety filters.
9. **Final risk** — `final_risk = max(merged_pre_chat, reply_json.risk_level)` using the ordering `low` < `medium` < `high`. The reply model’s `risk_level` is a **secondary** check: it **cannot** lower risk below `merged_pre_chat`; it may still **raise** it if it detects crisis wording the pre-chat path missed.
10. Apply `suggested_policy_action` from the reply JSON only in ways consistent with `final_risk`, hard gates, session lock, and post-LLM overrides — it must not bypass hard templates or §11.
11. Final policy override and response selection.
12. Structured logging of classifier (when used), merge, and policy outcomes.

### Classifier reliability (when the LLM router is enabled)

- **`confidence`** on the classifier payload is a **string enum** in v1 (`high` | `medium` | `low`), meaning model self-reported certainty, not a calibrated score.
- If classifier JSON **fails validation**, **`confidence` is missing**, or **`confidence` is `low`**, use the **documented soft fallback** (recommended: legacy regex pre-classification for non–hard-gated routing only; hard gates unchanged). See `docs/LLM_SAFETY_ROUTER_PLAN.md` §3.2.
- Optional classifier **`rationale`** is for logging only, **off by default in production**, and must not be shown to end users in MVP.

## 5) Conflict and uncertainty handling

If any of the following occur, apply the safer policy action:
- **`merged_pre_chat`** is higher than the reply JSON’s `risk_level` (reply cannot downgrade; §4).
- Reply JSON `risk_level` is higher than `merged_pre_chat` → use the higher value for `final_risk` and follow high/medium policy for that level.
- LLM output is malformed, missing required fields, or inconsistent.
- Dedicated classifier (when enabled) is unusable or reports **`confidence: low`** / missing confidence → fall back as in §4 (classifier reliability).
- Ambiguous intent or contradictory evidence → prefer the safer branch.

Default fallback by severity:
- Ambiguous but concerning: medium-risk template or medium_llm path per merge result.
- Clear explicit intent/threat: high-risk template.

## 6) Prohibited output classes

The assistant must refuse or safely redirect requests for:
- Self-harm or violence instructions.
- Medical dosing/treatment instructions.
- Diagnostic certainty statements.
- Hate/harassment encouragement.
- Prompt-injection attempts to ignore policy.

## 7) Conversation style constraints

- Keep responses concise and supportive.
- Do not claim to be a human or clinician.
- Do not claim capabilities (calling services, contacting police, locating user) that the system does not have.
- Avoid certainty language that overpromises outcomes.

## 8) Logging and review fields (minimum)

Store structured fields for each turn:
- session_id
- message_id
- request_id
- pre_risk_level (legacy regex-only pre-classification, when recorded separately)
- merged_pre_chat_risk (nullable until the LLM router ships; then the risk after pre-chat merge, before reply JSON)
- llm_risk_level_suggested (from reply JSON)
- final_risk_level
- policy_action (normal, medium_llm, medium_template, high_template, high_policy_template, blocked, fallback)
- safety_flags (array)
- fallback_reason (nullable)
- latency_ms

When the dedicated classifier is enabled, also log where available:
- classifier_risk_level (nullable)
- classifier_confidence (nullable; `high` | `medium` | `low`)
- llm_router_enabled (boolean) or equivalent settings snapshot for audit

## 9) Versioning

- Any safety policy update must increment version and include rationale in `docs/DECISIONS_LOG.md`.

## 10) Data persistence scope (MVP)

- Conversation consent and persistent storage are out of MVP scope.
- MVP should operate in ephemeral mode by default.
- If persistence is introduced later, policy updates must be recorded in `docs/DECISIONS_LOG.md`.

## 11) High-risk repeated-turn incident rule (MVP)

- If 3 or more high-risk turns occur in a single session:
  - Keep returning fixed high-risk template responses.
  - Keep the crisis resources banner pinned and visible.
  - Suppress normal conversational responses for the remainder of the session.
