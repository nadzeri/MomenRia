# Midtrans review and pricing release checklist — 10 October 2026

Local implementation follows the [approved plan](superpowers/plans/2026-10-10-midtrans-website-requirements.md): three lifetime successful free pictures per account, then IDR9,900 per new picture before generation. Corrections to an existing picture, greetings, downloads and format exports stay free. Both free and paid downloads use clean full-quality masters. No production deployment, customer-data migration, live payment, real AI generation or external support message was performed.

## Website requirement evidence

| Requirement | Implemented locally | Evidence still required before Midtrans/public release |
|---|---|---|
| R1: accessible products and ordering | Public catalog/description, price and quota copy; account preparation; fourth-picture checkout; backend settlement, generation and download. | Public HTTPS access, approved service examples and real sandbox purchase/delivery demonstration agreed with the merchant reviewer. |
| R2: terms and refund policy | `/terms/`, `/refunds/`, `/privacy/` work without JavaScript; linked in footer and checkout; unchecked policy acknowledgement and stored versions; failed-generation resolution and audited refund outcomes. | Final legal identity/address, usage rights, tax/fees, refund eligibility/request/response/resolution deadlines and manual-remedy ownership. Check actual channel refund capability. |
| R3: contact | `/contact/` publishes owner-provided MomenRia, support@momenria.id and +62 822-2666-9926; order-linked support remains private. | Monitor and test the real email/phone, approve support hours/escalation, match operator identity to Midtrans registration. |
| R4: Rupiah | Immutable new generation offer/order/charge is IDR9,900. Historical IDR19,900 orders/offers retain their original receipts. Server validates amount/currency/status. | Verify merchant sandbox reports and production tax/fee treatment. |
| R5: same-site checkout | Core QRIS instructions and order status render on the application's origin; validated environment-specific QR image URLs; no checkout redirect. | Observe the real flow on momenria.id; validate QRIS acquirer and one-phone wallet behavior; confirm channel-specific handoff expectations with Midtrans. |

Planned public origin is `https://momenria.id`. The local DNS check could not resolve it; public reachability is unverified. This is not evidence that the domain is unavailable from every network.

## Pricing and delivery acceptance

- [x] Three server-enforced lifetime successful free creations; owner lock and unique slots protect concurrent requests across projects. Failed attempts release reservations; uncertain attempts hold them. Deletion does not replenish consumed quota.
- [x] Fourth unpaid generation is blocked; one paid order prepares and queues one frozen generation only after verified settlement. Duplicate/lost responses, repeated notifications and concurrent callbacks do not create another purchase or dispatch.
- [x] Corrections use an authorized root and remain free after quota exhaustion. Full-quality downloads and master-based padded exports retain account/root authorization and expiry. No brand watermark is added.
- [x] Verified full refunds revoke root/derived access and stop dispatch. Requested/processing/uncertain refunds retain access. Order history, support and reconciliation remain available when new checkout is paused.
- [x] Disposable historical migration tests preserve paid/pending orders, old prices, revoked grants/refunds and retained/deleted/expired cohorts. Audit defaults to dry-run; applying requires staff/reason and resolved legacy jobs/payments. Missing/changed masters are quarantined rather than reconstructed.
- [ ] Review and apply the historical audit on the real backed-up database through the [cutover procedure](operations.md#three-free-picture-cutover). No retrospective charges.
- [ ] Verify real generated quality/likeness, processor eligibility/privacy/deletion and cost of three free creations, supported corrections and payment fees against IDR9,900. Synthetic output or resizing to 2048 pixels does not establish quality or margin.

## Local verification

All tests use isolated databases, private media and example pictures. Fake AI/payment is limited to `APP_ENV=test`. No existing customer database or `.env` credentials are used by the browser harness. Paid browser artifacts use their own directory so concurrent suite cleanup cannot delete another suite's traces.

| Check | Observed result |
|---|---|
| Full Django suite on PostgreSQL | 175/175 passed, including admission, order/webhook and refund races; no concurrency skips. |
| Full Django suite on SQLite | 175 run: 169 passed, six PostgreSQL concurrency tests skipped. |
| General Playwright desktop/mobile | 60/60 passed. Includes anonymous/no-JavaScript policies, quota-aware isolated accounts, ownership, consent, downloads and recovery. |
| Separate payment Playwright desktop/mobile | 4/4 passed. Real fake-gateway three-free-to-paid journey plus explicitly mocked QRIS pending/uncertain/failed/refunded presentation. |
| Node prototype suite | 4/4 passed. Archived prototype was not modified. |
| Migration drift | `makemigrations --check --dry-run`: no changes detected. |
| Deployment settings check | `check --deploy`: no issues under separate synthetic production settings with admissions/payment disabled. This is not a deployment or infrastructure audit. |

Run the backend suite with an explicitly isolated PostgreSQL URL/media root:

```bash
.venv/bin/python manage.py test momenria accounts catalog commerce processing projects operations --noinput
.venv/bin/python manage.py makemigrations --check --dry-run
npx playwright test
npx playwright test --config=playwright.payments.config.js
npm test
```

The ordinary browser harness uses ports 8765/8767; the paid harness uses 8775/8777. Never substitute production credentials or database/media paths. UI QRIS screenshots use a labelled simulated QR, intercepted responses and test-only CSP setup; they do not prove provider connectivity, physical scanning or refund transfers. Original download tests compare master hashes/dimensions, not just HTTP success.

A fresh whole-branch review found payment recovery, historical refund/access, paid deletion and retention gaps. Regression tests reproduced them before fixes. They now cover lost-charge QR recovery, late duplicate/revoked historical payments, partial-refund totals and remaining obligations, historical refunded corrections, attributable quota/grant/quarantine changes, root-based correction expiry and physical quarantine cleanup. Refunding an extra duplicate payment preserves original funded access. See [implementation evidence and decisions](midtrans-implementation-evidence.md).

## Merchant and production gates

- [ ] Finalize policy/contact inputs above and publish matching dated policy versions. Confirm support and manual refund procedure are staffed.
- [ ] Confirm Midtrans registration/channel approval, QRIS acquirer, environment-specific server keys and publicly reachable HTTPS webhook endpoints. Keep new checkout disabled until approved; keep provider reconciliation configured if payments already exist.
- [ ] In the merchant-approved sandbox/review environment, verify charge identity/timeout recovery, real QR image instructions, wallet/issuer behavior, settlement notifications plus authenticated status, amount/currency, late/duplicate settlement and refund capability/evidence. Use private reviewer accounts and consented example images.
- [ ] Retain existing email delivery/recovery, MFA/security, privacy/guardian-consent, real likeness/face mapping, provider retry/cost, budget/capacity, monitoring, off-host backup/tombstone restore and incident-owner gates.
- [ ] Package public URLs, product/price examples, policy/contact evidence, complete purchase/delivery recording and sandbox references for review. Agree with Midtrans whether sandbox evidence is sufficient; do not present mocks as a live store.
- [ ] Separately authorize controlled live charge/refund and deployment when all gates close. Roll back by pausing admissions/new checkout while preserving usage/history, authorized downloads and in-flight payment/refund reconciliation.

## Source requirements

The five supplied screenshots define R1–R5. All ten pages of `Midtrans TNC Template Jan 13 2017.pdf` were reviewed as a topic checklist for service/digital goods, not copied retail/subscription clauses or instructions to the assistant. Current primary references checked during planning: [website criteria](https://docs.midtrans.com/docs/what-are-the-website-or-application-criterias-for-registering-a-midtrans-account), [Core QRIS](https://docs.midtrans.com/reference/qris), [transaction status](https://docs.midtrans.com/reference/transaction-status), [custom expiry](https://docs.midtrans.com/reference/custom-expiry-object), [refund capabilities](https://docs.midtrans.com/docs/what-payment-method-that-have-refund-feature), and [refund operation](https://docs.midtrans.com/docs/how-can-i-refund-transaction). Merchant-specific validation remains necessary.
