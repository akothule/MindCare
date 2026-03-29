# MindCare Post-MVP Backlog

Features intentionally out of scope for MVP that can be added later.

## 1) Persistence, consent, and retention

- Add conversation persistence in database.
- Add consent UX for storing anonymized conversations.
- Enforce retention/deletion policy for stored conversation data.

## 2) Data layer and infra expansion

- Implement managed database integration (Postgres/Firestore).
- Add schema migrations and data access layer.
- Introduce robust analytics/event pipelines.

## 3) User identity and accounts

- Add optional user accounts/authentication.
- Link sessions to users for long-term continuity.
- Re-evaluate privacy/compliance implications when identity is introduced.

## 4) Product and UX enhancements

- Add mood check-ins and lightweight tracking experiences.
- Add richer coping tool modules and guided exercises.
- Add user feedback loops with review dashboards.

## 5) Monitoring and operations

- Add dashboards and production-grade alerting.
- Expand observability for safety events, latency, and reliability trends.
- Formalize incident response playbooks for high-risk traffic patterns.

## 6) Policy and localization improvements

- Revisit age-specific policy behavior/resources if needed.
- Add multilingual support and localized crisis resources.
- Expand regional guidance beyond generic + U.S. resource defaults.

## 7) Platform evolution

- Move from embedded prototype UX to dedicated full web app.
- Add polished static pages (About, Privacy, Resources) and product navigation.
