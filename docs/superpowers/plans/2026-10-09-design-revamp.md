# MomenRia design revamp

Goal: implement every approved design audit recommendation and independently verify the complete application against the original 40-point design and 20-point technical rubrics.

Spec: `docs/design-audit-2026-10-09/README.md`, PRODUCT.md and DESIGN.md.
Architecture: Django APIs and allauth accounts, existing vanilla JS SPA, shared CSS. Reuse current ownership, validation, rate limiting, native dialogs and immutable results. No new runtime dependencies or payment/provider activation.

## Tasks and interfaces

1. Backend recovery, support and review state: public account-access requests with generic receipt and network rate limiting; owner ticket replies; latest feedback on each result/slot; project pagination; job timestamps; session operating mode. Reach APIs, models/migrations, admin, OpenAPI and meaningful security/state tests. New replies are immutable messages; old staff reply field remains compatible.
2. Account and operator UI: compact account settings, contextual navigation and differentiated destructive actions; clear verification/reset recovery path; truthful public recovery form. Reach templates, dedicated account CSS, admin and account tests. Depends on Task 1 public recovery endpoint.
3. Main flows: compact studio, progress/slots/reachable primary action; persistent face review and contextual correction; catalog return state; grouped/paginated library and direct project retrieval; focus-safe status updates and visible offline state; upload guidance/preview/errors; comparison, greeting and save refinements; truthful mode/privacy/expiry; parallel startup. Reach server.js, server.css, app.html and E2E tests. Consumes Task 1 interface additions.
4. Verification: run meaningful backend, node and desktop/mobile browser suites; inspect public, signed-in, dialogs, account/MFA/admin and error states at narrow/wide/zoomed viewports; scan rendered pages; fresh independent design and technical reviews; fix findings and repeat verification as changes require. Preserve evidence and score only demonstrated criteria.

## Acceptance matrix

F01 public account recovery; F02 mobile studio; F03 persistent face review/repair; F04 focus and live progress; F05 truthful expiry; F06 support replies; F07 account hierarchy; F08 catalog return state; F09 library pagination/direct project; F10 mobile comparison; F11 upload guidance/errors; F12 actual mode/pre-upload limits/prototype archive; F13 independent public startup; F14 readable tokens/type/focus; F15 CTA hover contrast; F16 placeholder contrast; F17 heading semantics.

All catalog collections/templates, private lifecycle, character references, template switch, processing uncertainty/retry, greetings, exports, help, privacy/terms, auth/MFA, administration, startup/noscript/unknown routes must remain usable. Paid features stay gated. No unsupported production delivery, privacy, likeness, screenreader or physical-device claims.
