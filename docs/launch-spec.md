# MomenRia launch scope — 25 September 2026

Ship a usable Bahasa Indonesia family portrait beta without payments. Preserve the existing Django ownership, immutable template/result versions, cost controls, private files, and durable worker. Payment integration, checkout, paid conversion and merchant onboarding are outside this release.

## Customer experience

- Public landing page explains separate-photo family portraits, shows actual template examples, explains AI limitations, and links directly to catalog and instructions.
- Catalog lists the three existing concepts with names, descriptions, attire, people counts, search, filters, details, and direct studio entry. Only published, approved variants are selectable. More concepts require assets, face slots and benchmark evidence; duplicating existing art is not catalog expansion.
- Studio preserves the exact draft across navigation/reload, shows uploaded thumbnails, consent, validation, expiry and service status. Processing cannot accept duplicate actions or silently overwrite forms while polling.
- Results show the exact selected version, references, expiry, feedback, correction availability, greeting editor, zoom and a free watermarked preview download. No paid checkout is offered when the provider is disabled. Existing master entitlement checks remain intact.
- Complete guide, FAQ/help, privacy, terms, photo library and account views, including logged-out, empty, unavailable, failed and expired states. Do not invent support response hours, provider approvals or quality claims.
- Phone and desktop layouts, labeled controls, visible focus, accessible dialogs and reduced motion.

## Release requirements

- `PAYMENT_PROVIDER=disabled` for this release.
- `PUBLIC_ACCESS=false` for real customer data; production must reject shared-owner access.
- Sources default to 7 days; results default to 30 days. Display actual configured values and exact result expiry.
- Creation and correction have no usage-count quota (updated 26 September 2026). Preserve one active job per project, idempotency, source eligibility and service capacity controls. Server remains authoritative.
- Keep real AI disabled until provider privacy, cost and likeness evidence exists. Synthetic browser tests are not likeness benchmarks.
- Never use the existing database, customer media, paid API calls or shared-owner production configuration for automated browser tests.
- No new UI framework or build pipeline. Add Playwright as a development dependency only.

## Acceptance

Automated browser coverage must exercise public navigation, template filtering/selection, account forms, authenticated upload through actual Django endpoints, draft reload, fake worker completion, preview delivery, correction/greeting/version selection, support, deletion, keyboard controls and mobile overflow. Backend checks must continue proving ownership and expiry. Separate infrastructure checklist must record real provider evaluation, email delivery, PostgreSQL races, backup/restore, monitoring and physical-device validation before opening admissions.
