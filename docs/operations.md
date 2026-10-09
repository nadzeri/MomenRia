# MomenRia operations

## Release gates

Production requires `PUBLIC_ACCESS=false`; shared-owner mode is rejected at startup. `PUBLIC_ACCESS=true` is for isolated test demos only. Anyone reaching such a demo can access that owner's workflow and data; never upload real customer photos there. Admin/operator authentication and MFA remain mandatory.

The current pricing release provides three lifetime successful free creations per account, then IDR9,900 per new picture. Corrections to the same picture and full-quality downloads remain free. Keep new paid checkout paused until the merchant, channel, policy, refund and AI/privacy gates close; see `docs/midtrans-review-checklist.md` and `docs/launch-readiness.md`. If money is already in flight, keep the payment provider configured for reconciliation while `PAYMENT_CHECKOUT_ENABLED=false` pauses new purchases.

Keep admissions disabled until owner records decisions D01 to D12 from technical requirements. Hard blockers for real customer processing:

- production host, domain, HTTPS, external backup destination, and measured capacity;
- verified 9Router generation and correction contract, exact model route, provider eligibility, cost ceiling, retries, and deletion behavior;
- passing two-, three-, and four-person likeness benchmarks for each published variant;
- for the later paid release only: merchant-approved QRIS provider, sandbox callback endpoint, refund process, price, and policy;
- SMTP domain delivery, support hours, retention policy, child/guardian policy, and incident owner.

## Deployment and rollback

1. Build immutable application image and run tests against PostgreSQL.
2. Back up database, source volume, character-reference volume, result volume, configuration, secrets, and deletion tombstones.
3. Run `python manage.py migrate --noinput` as separate migration service.
4. Start web, worker, and maintenance processes. Check `/health/live` and internal `/health/ready`.
5. Verify account recovery, synthetic draft, queue readiness, and payment connectivity without a live charge.
6. Enable admissions only after smoke checks.

The web service needs write access to the result volume because greeting versions are rendered synchronously by Django. Keep that volume private. Caddy terminates HTTPS and sets `X-Forwarded-Proto`; Django trusts this header. Never expose the web container directly to an untrusted network. `Referrer-Policy: same-origin` permits account form CSRF validation while withholding referrers from other origins.

Rollback application image only while schema remains compatible. Do not restore an older database over new orders. Reconcile payment provider records before reopening admissions.

### Three-free-picture cutover

1. Pause new paid checkout with `PAYMENT_CHECKOUT_ENABLED=false` and disable new admissions. Preserve configured payment reconciliation, history, deletion and authorized downloads. Back up database/media and deletion tombstones before migrating.
2. Drain legacy creation/correction jobs. Reconcile pending or uncertain historical download payments, including locally cancelled/expired/failed orders whose provider outcome is unverified. The audit refuses `--apply` while these records remain unresolved.
3. Apply current additive migrations on an isolated restored copy first. Run `python manage.py reconcile_pricing_history` without `--apply`; inspect every owner/result report. Real successful historical creations count even when deleted/expired; synthetic results, corrections and greetings do not. Incomplete history remains blocked for operator resolution. Existing receipts and activated offers keep their amounts.
4. Confirm the dry-run against retained original master files. Missing/changed masters are reported and, on apply, quarantined with support resolution. Revoked/refunded, expired or deleted pictures are never restored. Clean previews are rebuilt from verified masters; original bytes remain unchanged.
5. An active staff operator may apply the reviewed migration using `python manage.py reconcile_pricing_history --apply --operator staff@example.com --reason 'Approved reviewed historical pricing cutover'`, substituting the actual operator and reason. This is a production data change; do not run it merely to prepare review evidence. Re-run the dry-run and compare owner quotas, master hashes, grants, quarantines and payment reconciliation.
6. Verify the active generation offer is IDR9,900, policy versions and merchant configuration are approved, and real AI/privacy/quality/economics/infrastructure gates are closed. Start maintenance/reconciliation before workers; reopen admissions and new checkout last.

Rollback pauses new purchases and, if needed, new creations. Keep migrated lifetime usage, stored order amounts and grants; retain reconciliation and refund processing for money in flight. Do not undo quota history or restore an old database over new orders. Review [Midtrans release evidence](midtrans-review-checklist.md) before activation.

## AI uncertainty

Timeout after possible dispatch is `uncertain`, not failed. Keep the job and cost reservation locked. Do not retry until provider request lookup proves non-execution or operator records resolution. Never route customer photos directly around 9Router.

### Uncertain-attempt runbook

1. Pause admissions if several jobs become uncertain or worker heartbeat alert is active.
2. Record operator, reason, job, attempt, gateway request ID, and timestamps. Do not open source images unless owner grant permits it.
3. Query 9Router by same provider request ID. If completed, validate and finalize once. If provider proves request never ran, mark attempt non-billable and requeue once. If status is unknown, keep job uncertain and reservation locked.
4. Reconcile billed cost before releasing reservation. Notify affected owner through support record. Resume admissions only after route health and duplicate-execution risk are known.

### Gateway-outage and admission-pause runbook

Set global `AdmissionControl.enabled` false with audit reason. Existing downloads, payment reconciliation, deletion, and support continue. Do not reroute private photos to another processor without eligibility and benchmark approval. Restore route, run non-customer contract fixture, verify cost and response limits, then re-enable within configured budget and concurrency caps.

## Payment and paid-file failure

Browser return does not grant access. Signed webhook plus authenticated provider status must match environment, order, amount, currency, settled state, and fraud status. Duplicate notifications are idempotent. If paid media is unavailable, preserve order history, open support resolution, retry delivery, then use one idempotent refund request if delivery cannot be restored.

### Late or duplicate settlement runbook

1. Keep payment event and raw provider reference; never grant from browser return.
2. Compare provider lookup with merchant reference, transaction ID, amount, currency, environment, QRIS method, fraud state, and exact result version.
3. For live retained result, commit one entitlement. For expired/deleted/unavailable result, keep fulfillment blocked and create support resolution.
4. Link duplicate provider transaction to same order or escalate as duplicate settlement. Do not create second entitlement or replacement order automatically.

### Refund runbook

Confirm delivery cannot be restored and the approved policy permits refund. Create one full-amount request through the operator API (staff MFA and recent authentication, stable Idempotency-Key) or use the automatically raised failed-generation request. Different keys cannot create a second outstanding/successful full refund. Issue the refund in the approved Midtrans dashboard procedure; this application does not submit a refund transfer.

Open the Refund record in staff admin and choose **Record external refund outcome**. Enter the exact order amount in IDR, external reference, verified dashboard/report or approved manual-transfer evidence, outcome and audit reason. Staff MFA, refund-change permission and recent authentication protect submission. Audit events retain actor, timestamp, amount, reference, reason and evidence. Processing/uncertain outcomes do not revoke access. Verified success revokes future root/derived access and stops dispatch; completed records cannot be rewritten, and payment replay does not restore access. Already downloaded copies cannot be recalled.

On timeout, query the same provider request before retrying; never generate a new refund identity. Reconcile against settlement reports daily. If the provider method/window cannot provide the approved remedy, staff must verify an owner-approved manual-transfer fallback and record its bank/report reference and verified completion. Final eligibility, support deadlines and fallback ownership must be approved before release; live submission remains an external release gate.

### Paid-file failure runbook

Pause new purchase of affected version. Verify media hash, expiry, entitlement, and storage health. Restore only from eligible backup after tombstone replay. If exact purchased bytes cannot be restored within published support window, use refund runbook. Never substitute another generated version.

## Deletion

Accepted deletion immediately soft-deletes project, increments deletion epoch, cancels active jobs, revokes support grants, and queues physical removal. Worker checks epoch before publication. Maintenance deletes tracked source/character-reference/result files and retries failures. Late payment never restores deleted media.

### Source expiry and deletion-retry runbook

Maintenance removes source, thumbnail and dependent character sheets after policy expiry or withdrawn source consent and marks record expired. Result expiry revokes entitlement and ends fulfillment. If deletion task fails, keep project inaccessible, inspect error code without logging paths or bytes, repair storage/permission fault, and let same task retry. Alert at one hour. Confirm tracked files, orphan sweep, entitlements, grants, jobs, and paid fulfillment are closed before resolving incident.

## Backup and restore

Use nightly coordinated PostgreSQL dump plus matching immutable-media manifest and files. Encrypt backups with separately stored key. Keep deletion tombstones outside restore set. Before restored data becomes accessible: replay tombstones and expiry, verify media hashes, reconcile paid orders, and quarantine any photo whose deletion history is missing. Paid beta requires owner-controlled copy outside production host.

### Backup runbook

Pause catalog/admin writes or use one coordinated snapshot boundary. Export PostgreSQL with schema and data, copy source/character-reference/result volumes plus hashes, copy versioned template/config artifacts, and separately copy tombstone journal. Encrypt and send to D10 destination. Test archive integrity, record snapshot timestamp and checksum, then atomically update `BACKUP_MARKER_PATH`. A marker without verified off-host bytes is invalid.

### Restore runbook

1. Keep admissions, worker, web access, and payment fulfillment stopped. Restore into isolated clean host and database.
2. Restore media matching database snapshot. Apply every tombstone newer than snapshot; run expiry and deletion maintenance. Quarantine objects missing tombstone history or expected hash.
3. Reconcile all orders and refunds since snapshot against provider, preserving exact result identity. Apply current migrations and run ownership, readiness, synthetic-flow, and file-integrity checks.
4. Obtain incident owner approval. Start web and maintenance first, then payment reconciliation and worker. Reopen admissions last.

### Secret-rotation runbook

Pause admissions and payment creation. Rotate one credential class at a time: Django/session secret invalidates sessions; database roles require connection restart; SMTP, 9Router, and payment keys require provider-side revoke after new key verifies. Update secret store, restart affected services, run non-billable connectivity checks, confirm old key fails, and record actor/reason. Never paste secret values into tickets or logs.

## Incident response

Pause admissions, preserve paid delivery and reconciliation, rotate affected credentials/sessions, scope exposed objects, and record actions. Logs must never contain cookies, authorization headers, image bytes, prompts with private content, processor URLs, or payment credentials.

### Privacy-incident runbook

Assign D11 incident owner and timestamp. Stop affected route, revoke grants/sessions/credentials, preserve minimal audit evidence, and identify owners, objects, processor, exposure window, deletion state, and legal notification deadline. Do not copy customer images into incident tools. Complete containment, owner communication, processor deletion confirmation, and corrective controls before reopening. Publish support hours, escalation contact, refund policy, and notification procedure before paid pilot.

## Character-reference rollout

Follow [character reference implementation and evaluation](character-consistency-operations.md) for immutable template preparation, A–E staging evaluation, generated-sheet review, cost reconciliation and rollback. Preparation jobs reserve AI budget without consuming creation/correction allowances. Include the private `characters` volume in coordinated backups, tombstone replay, hash verification and expiry/deletion drills. Never approve likeness from synthetic test output.
