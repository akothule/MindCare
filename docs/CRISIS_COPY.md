# MindCare Crisis and Support Copy (MVP v0.1)

Use this file as the source of truth for template-based crisis responses.

## 1) High-risk template (U.S.)

I'm really glad you shared this. I am concerned about your immediate safety.

You deserve support right now from people who can help in real time:
- Call or text **988** (Suicide & Crisis Lifeline, U.S.) any time, 24/7.
- If you may act on these thoughts now, call **911** right away.
- If possible, move to a safer place and contact a trusted person who can stay with you.

I am not an emergency service, but your safety matters and reaching out now can help keep you safe.

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

- **High-risk:** Use the §1 body **verbatim** (no improvisation of hotlines or wording). Then **append** the §5 location disclaimer line so the full user-facing `reply_text` is: §1 body + disclaimer. Spacing (newline vs paragraph) is an implementation detail; content must not vary from approved copy.
- **Medium-risk:** Use the §2 body verbatim when serving the medium template, then append the §5 disclaimer the same way when that response is crisis/support safety messaging.
- Medium-risk template can be used as fallback for ambiguous distress.
- Do not let the LLM improvise hotline numbers.
- All numbers and wording changes require review and version bump.

## 5) Location disclaimer line (for global access)

Append this line **after** the §1 or §2 template body whenever that template is used (so the disclaimer is part of the same message, not a separate policy conflict):

"If you are outside the U.S., local emergency and crisis services may be different. If you are in immediate danger, contact your local emergency number now."

## 6) High-risk follow-up UX rule

After returning the high-risk template, keep chat available and display a persistent crisis resources banner in the UI.
