# MomenRia launch readiness — 25 September 2026

**Decision: customer experience improved and locally verified; production launch remains gated. Payments are excluded.**

Implementation plan: [launch readiness plan](superpowers/plans/2026-09-25-launch-readiness.md). Scope: [launch specification](launch-spec.md).

## Delivered

| Area | Current behavior |
|---|---|
| Landing | Responsive Indonesian product story, real template samples, clear free-preview CTA, three-step guide, FAQ and privacy explanation; no invented testimonials or likeness metrics |
| Catalog | Three genuine existing concepts, search, people/occasion filters, no-match recovery, details, stable direct studio URLs |
| Studio | Exact draft resume, owner-scoped photo thumbnails, expiry, permission checkbox, file validation, disabled generation with a reason, processing locks and actionable failures |
| Results | Named free watermarked download, source comparison, zoom, version selection, explicit feedback, one shared correction, local greeting edit/removal, expiry and deletion |
| Content | Complete guide, help/FAQ, support history and replies, image-grant revocation, privacy and non-payment terms; unknown provider/legal/support commitments remain disclosed |
| Accounts | Branded login/signup/reset, working email-only signup and verification, password validation, consistent Indonesian locale |
| Payment exclusion | Checkout and order navigation hidden when `PAYMENT_PROVIDER=disabled`; master entitlement protection retained |
| Privacy | Private accounts by default, production shared-owner rejection, obvious shared-demo warning, owner-only and expiry-checked media |
| Reliability | Pending forms cannot lose edits; delayed responses cannot replace another route; failed-job retries get a new identity while ambiguous retries retain theirs |
| Performance | Display-only WebP derivatives total 213,460 bytes versus 6,527,239 bytes for the original PNGs (96.7% smaller); immutable generation originals unchanged |

No live AI call, payment, email to an external recipient, or deployment was performed. Existing `.env`, customer database/media and running Docker stack were not changed. This workspace has no Git metadata, so changes are files on disk rather than commits.

## Verification

- **Playwright: 22 passed**, 11 scenarios each on desktop Chromium and iPhone-sized WebKit. Full workflow uses actual Django sessions, uploads, face validation, durable synthetic worker, greeting render, downloads, support and deletion. Targeted pause/expiry/latency/retry tests simulate specific API responses and are named accordingly.
- **PostgreSQL: 55 passed**, including twenty-request admission contention and shared-budget concurrency. Ran against a separate temporary PostgreSQL 18 container, then removed it. Existing database untouched.
- **SQLite: 55 discovered, 53 passed, 2 PostgreSQL-only cases skipped.** Local SQLite uses immediate transactions to avoid lock-upgrade failures; production requires PostgreSQL.
- **Node: all four existing suites passed**, covering original prototype state/startup/studio behavior and production upload multipart schema.
- **Django migration check:** no model changes/migrations required.
- **Django production configuration check:** no issues under explicit HTTPS/private-account/SMTP-shaped configuration. Credentials were test values; this proves settings validation, not real SMTP delivery or infrastructure readiness. Default development settings correctly produce six deployment warnings.
- **Visual inspection:** desktop landing and results; mobile studio, landing and account form. Full-page screenshot capture waits for image decoding, including offscreen lazy images.
- **Independent review:** three important timing/retry findings reproduced in browser tests, fixed, and checked again. No critical security regression reported. Reviewer did not independently validate external provider, SMTP, legal, backup or physical-device gates.

Run locally:

```bash
.venv/bin/python manage.py test --noinput
node --test test-*.cjs
npm ci
npx playwright install chromium webkit
npm run test:e2e
npm run test:e2e:report
.venv/bin/python manage.py makemigrations --check --dry-run
```

Reports and screenshots are in `playwright-report/` and `test-results/`. Playwright owns a temporary loopback server; do not point the destructive lifecycle suite at production. Setup follows Playwright's [web server support](https://playwright.dev/docs/test-webserver). Same-origin referrer policy preserves account form checks described in [Django's CSRF documentation](https://docs.djangoproject.com/en/5.2/ref/csrf/).

## Bugs resolved during preparation

1. Signup previously crashed because allauth assumed a username field absent from the custom user model.
2. `no-referrer` caused real browser login POSTs to carry an unusable origin; account forms now keep same-origin context with CSRF validation intact.
3. Greeting changes rendered over prior greeting pixels. They now walk to the nearest non-greeting ancestor, preserving corrected faces while replacing text.
4. The Docker web container mounted results read-only even though greeting saves write new result files.
5. Existing results depended on the live catalog; pausing a template could break rendering. Projects now carry their own template metadata.
6. Source expiry, pending work and used allowances were not reflected consistently in controls.
7. Preview downloads were absent even though the original product scope includes them.
8. Delayed async results could reroute users or erase support drafts; pending forms remained editable and discarded new text.
9. Failed processing retries reused a completed request identity and returned the previous failure instead of a new job.
10. Disabled AI could be advertised as accepting work. Both catalog status and admission now reject that condition.

## Remaining launch sequence

Every item below is a release gate, not evidence inferred from passing automated tests.

| Priority / stage | Action | Owner | Exit evidence |
|---|---|---|---|
| P0 — product policy | Approve operator identity/contact, actual support hours, privacy/terms, child/guardian rules, processor disclosure and incident ownership | Product owner | Final published copy matching real arrangements; no unverified provider-retention promise |
| P0 — AI contract | Configure and verify generation and targeted-edit routes, eligible processing, deletion, bounded cost and uncertain-job lookup | Product owner + provider | Real consented requests, response contract, measured costs and safe failure/reconciliation behavior |
| P0 — template quality | Benchmark each 2-, 3- and 4-person variant, including relatives with similar features, glasses, hijab, varied ages/skin tones and correction regressions | Product owner | Per-variant approved benchmark records; no wrong-person or surviving sample identity; publish only passing variants |
| P0 — production infrastructure | HTTPS domain, production secrets, isolated accounts, PostgreSQL roles, private media, writable result volume for greetings, persistent worker/maintenance and configured result font | Operator | Clean deployment checks plus real health, upload, generation, greeting and deletion smoke tests |
| P0 — identity and security | Deliver real verification/reset email; exercise account isolation, staff MFA/re-auth and recovery | Operator | Successful mail delivery and real production-host auth checks |
| P0 — durability and incidents | Configure off-host encrypted backup, replayable tombstones, alerts; perform timed restore and uncertain-job/deletion drills | Operator | Recovered hashes and owner data, deleted data still inaccessible, alert delivery and incident runbook evidence |
| P0 — usability and capacity | Physical iPhone Safari/Android Chrome, slow upload, interrupted request, sleep/resume, keyboard/screen reader and enlarged text; measure resource limits and latency | Product owner + operator | No blocked primary action, silent data loss, cross-account access or uncontrolled cost; documented capacity |
| P0 — limited non-payment pilot | Set positive daily budget and verified capacity; enable admission only for approved templates | Product owner | Pilot feedback, per-face acceptance, failures, support effort, actual spend; explicit go/no-go decision before expanding |
| After validated launch — more templates | Add new licensed/synthetic concepts and people-count variants based on observed demand | Product owner | New art, correct face slots, frozen generation configuration and fresh benchmark evidence |

All corrections currently require valid source references. After source expiry, UI preserves downloads and directs users to support. A self-service flow to renew all expired references remains a product gap if post-expiry corrections are required; do not promise them before that flow exists and is tested. Private production admissions should remain disabled until the gates above close.

Payments, QRIS onboarding, merchant callbacks, refunds and paid conversion work remain outside this launch. They do not block a correctly bounded free-preview pilot.

## Execution decisions

- Kept the three original template concepts rather than inventing more “available” variants from reused art. Expansion follows per-variant quality evidence; cost is a smaller initial catalog.
- Kept free watermarked previews, matching the PRD and the default presented during this task. Full-resolution master downloads remain gated; changing that business choice needs an explicit access-policy change.
- Preserved test-only shared mode for existing demos, but refused it in production. Existing shared demo photos do not automatically become isolated customer accounts.
- Used a separate temporary database/container for testing and left deployment unchanged. Production readiness still needs the real environment checks above.
- Did not claim owner/provider-dependent evidence was complete. Legal approval, real likeness, SMTP delivery, backup restoration and physical-device behavior remain open until actually verified.
