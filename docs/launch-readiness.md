# MomenRia launch readiness — 10 October 2026

The three-free-picture pricing release is implemented and tested locally. Production remains gated. New paid checkout defaults to paused; no live charge, customer-data migration, deployment or external support message was performed.

## Current behavior

- Three lifetime successful new pictures per account, then IDR9,900 per new picture, paid before generation. Confirmed failures release free reservations; uncertain attempts retain them. Deletion never resets consumed quota.
- Corrections to the same root picture, local greetings, downloads and padded format exports remain free. Free and paid original downloads retain full-resolution master bytes, with no product watermark.
- Public terms, privacy, refund and contact pages work without JavaScript. MomenRia, support@momenria.id and +6282226669926 are owner-provided details.
- Core QRIS instructions stay on the site's order page. Server-verified status queues one frozen job. Requested/processing/uncertain refunds preserve access; verified full refunds revoke root and derived access and stop dispatch.
- Order history, support, deletion, authorized downloads and payment reconciliation continue while new checkout is paused.

## Local evidence

Backend tests cover pricing, concurrency on PostgreSQL, legacy schema/data cohorts, charge timeouts and replays, signed notifications plus authenticated status, amount/currency checks, expiry, deletion, ownership, paid failures, refunds and master/derived access. Schema migration tests pass on PostgreSQL and SQLite. Browser suites use isolated databases, example pictures, fake AI and fake payments; explicitly mocked QRIS rendering is not provider or physical-wallet evidence.

Current commands and evidence counts are recorded in [Midtrans review checklist](midtrans-review-checklist.md). The [September non-payment evidence](launch-readiness-2026-09-25.md) remains historical; its watermark, quota and checkout policies are superseded.

## Production gates

Finalize legal operator details, support hours, refund eligibility/deadlines and manual remedy ownership. Confirm the contact channels are monitored and match Midtrans registration. Confirm public HTTPS/DNS, merchant/channel approval, the approved QRIS acquirer, sandbox/production callbacks, real charge/refund reconciliation and one-phone wallet behavior. The local DNS check for momenria.id failed; public reachability is unverified.

Retain existing processor privacy/deletion evidence, consent, real likeness/face-mapping benchmarks, AI cost/retry contracts, security, verified email delivery, backup/tombstone restore drill, infrastructure capacity and incident ownership gates. Synthetic output and 2048-pixel resizing do not establish real likeness, image quality or margin.

Follow the audited cutover and rollback procedure in [operations](operations.md). Do not revert to unlimited free generation or disable reconciliation with money in flight. A controlled live charge/refund and deployment are separate release actions.
