# MomenRia operations

## Release gates

Production requires `PUBLIC_ACCESS=false`; shared-owner mode is rejected at startup. `PUBLIC_ACCESS=true` is for isolated test demos only. Anyone reaching such a demo can access that owner's workflow and data; never upload real customer photos there. Admin/operator authentication and MFA remain mandatory.

The current launch scope excludes payments. Keep `PAYMENT_PROVIDER=disabled`; QRIS, merchant onboarding, settlement and refunds below apply only to a later paid release. See `docs/launch-readiness.md` for the non-payment go/no-go checklist.

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

Confirm delivery cannot be restored and policy permits refund. Create one refund request using stable idempotency key and full amount. Submit through approved merchant procedure, then record provider refund ID, terminal state, operator, reason, and timestamps. On timeout, query same provider request before retrying; never generate a new identity. Reconcile against settlement report. Live submission stays disabled until D04 and D11 close.

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
