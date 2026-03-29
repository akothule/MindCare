# Claude Provider Checklist (Pre-Coding)

Use this checklist before integrating Claude into the MindCare backend.

## 1) Provider and model selection

- [ ] Choose initial model ID (example: `claude-3-5-sonnet-latest`).
- [ ] Record rationale for model choice (cost, latency, quality, JSON reliability).
- [ ] Define fallback model ID for outages or quota issues.
- [ ] Record expected latency target for one response (p95 under 8s overall API target).

## 2) API integration defaults

- [ ] Set request timeout (recommended initial: 20s hard timeout at provider call level).
- [ ] Set retry policy (recommended: max 1 retry, exponential backoff, retry only on transient 5xx/timeouts).
- [ ] Define max tokens/output length guardrails.
- [ ] Define deterministic request ID propagation from app to provider logs.

## 3) Structured output reliability

- [ ] Require strict JSON schema in prompt contract (`reply_text`, `risk_level_suggested`, `style_flags`).
- [ ] Add schema parser validation in backend before any response is returned.
- [ ] Define parse-failure fallback policy action (`fallback` with safe template).
- [ ] Add test case for malformed/non-JSON output.

## 4) Safety alignment

- [ ] Ensure system prompt references `docs/SAFETY_POLICY.md`.
- [ ] Ensure crisis responses are template-driven from `docs/CRISIS_COPY.md` and not improvised.
- [ ] Ensure post-LLM filters run for banned classes (self-harm instructions, violence instructions, meds/dosing, hate).
- [ ] Confirm 3+ high-risk session rule is implemented as policy override.

## 5) Privacy behavior (MVP)

- [ ] Confirm MVP runs in ephemeral mode (no conversation persistence).
- [ ] Confirm no storage of direct identifiers in MVP logs.
- [ ] If persistence is enabled post-MVP, add consent flow and retention policy in docs first.

## 6) Geographic and age handling

- [ ] Confirm global-access behavior with always-on location disclaimer line.
- [ ] Confirm U.S. resources plus generic emergency guidance are available in safety messaging.
- [ ] Confirm MVP uses one safety policy for all users (no age-differentiated behavior).

## 7) Policy and terms validation

- [ ] Review current Anthropic policy docs for allowed mental-health-adjacent support use.
- [ ] Record policy review date and reviewer initials.
- [ ] Record policy URL used during review.
- [ ] Add any provider constraints to `docs/DECISIONS_LOG.md`.

## 8) Observability and incident readiness

- [ ] Log provider latency, status, and error class per request.
- [ ] Log pre-risk, model-suggested risk, final risk, and policy action.
- [ ] Add alert threshold for provider failures (e.g., 5xx or timeout spike).
- [ ] Add alert threshold for unusual high-risk volume.

## 9) Go/no-go sign-off (before coding integration)

- [ ] All boxes above checked or explicitly deferred with rationale.
- [ ] Deferred items copied into a short "Known gaps" note in `docs/DECISIONS_LOG.md`.
- [ ] Team decision: proceed to implementation of provider adapter.
