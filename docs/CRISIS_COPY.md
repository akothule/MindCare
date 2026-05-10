# MindCare Crisis and Support Copy (MVP v0.1)

Use this file as the source of truth for template-based crisis responses.

## 1) High-risk template (U.S.)

I'm really glad you shared this. I am concerned about your immediate safety.

You deserve support right now from people who can help in real time:
- Call or text **988** (Suicide & Crisis Lifeline, U.S.) any time, 24/7.
- If you may act on these thoughts now, call **911** right away.
- If possible, move to a safer place and contact a trusted person who can stay with you.

I am not an emergency service, but your safety matters and reaching out now can help keep you safe.

## 1a) High-risk supporter / third-party template (U.S.)

Use when the user is primarily **worried about someone else’s safety** (e.g. a friend or family member) and the message still warrants the same **high** routing and resources—not when the user is clearly describing **their own** self-harm intent (use §1 for that).

I'm really glad you reached out. When someone you care about may be unsafe, that can feel scary and heavy to carry alone.

You deserve support too. In the U.S., these resources can help you figure out next steps:
- Call or text **988** (Suicide & Crisis Lifeline) any time, 24/7 — you can ask how to help someone else or get guidance during a crisis.
- If someone may be in immediate danger, call **911** right away.
- If you can, stay with them when it's safe to do so, reduce access to anything they could use to hurt themselves if it's safe to do so, and help them connect with a trusted person or professional.

I'm not an emergency service, but your care for them matters and trained responders can help.

API `policy_action` is `high_supporter_template` (vs `high_template` for §1).

## 1b) High-risk policy / refusal template (U.S.)

Use when the user asks for harmful how-to content, tries to override safety instructions, or similar—**not** when they are primarily expressing personal crisis ideation (use §1 instead).

I can't help with anything that could seriously harm you or others, and I won't follow instructions meant to get around how I'm meant to work.

If you are having thoughts of hurting yourself or ending your life, that matters—and you deserve real support. In the U.S., you can call or text **988** (Suicide & Crisis Lifeline) any time, 24/7. If you may act on these thoughts or you're in immediate danger, call **911** right away.

I'm not an emergency service, but reaching out to trained responders can help keep you safe.

Then append the same §5 location disclaimer as for §1.

## 2) Medium-risk support template (U.S.)

Thank you for being honest about how hard this feels. You don't have to carry this alone.

It may help to reach out to someone you trust today and connect with professional support:
- Call or text **988** for immediate emotional support.
- Crisis Text Line: text **HOME** to **741741**.
- NAMI HelpLine: **1-800-950-6264**.

If you feel in immediate danger, call **911**.

## 3) Resource-only panel copy (for frontend banner/card)

Need immediate support?
- 988 (call or text, 24/7, U.S.)
- Crisis Text Line: text HOME to 741741
- Emergency: 911

## 4) Usage rules

- **High-risk (crisis):** Use the §1 body **verbatim** (no improvisation of hotlines or wording). Then **append** the §5 location disclaimer line so the full user-facing `reply_text` is: §1 body + disclaimer. Spacing (newline vs paragraph) is an implementation detail; content must not vary from approved copy.
- **High-risk (supporter / third-party):** Use the §1a body verbatim, then append §5 the same way. API `policy_action` is `high_supporter_template`.
- **High-risk (policy / refusal):** Use the §1b body verbatim, then append §5 the same way. API `policy_action` is `high_policy_template` (vs `high_template` for §1).
- **Medium-risk:** Use the §2 body verbatim when serving the medium template, then append the §5 disclaimer the same way when that response is crisis/support safety messaging.
- Medium-risk template can be used as fallback for ambiguous distress.
- Do not let the LLM improvise hotline numbers.
- All numbers and wording changes require review and version bump.

## 5) Location disclaimer line (for global access)

Append this line **after** the §1 or §2 template body whenever that template is used (so the disclaimer is part of the same message, not a separate policy conflict):

"If you are outside the U.S., local emergency and crisis services may be different. If you are in immediate danger, please contact your local emergency number now."

## 6) High-risk follow-up UX rule

After returning the high-risk template, keep chat available and display a persistent crisis resources banner in the UI.
