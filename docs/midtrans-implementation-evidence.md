# Midtrans implementation evidence — 10 October 2026

Implemented locally on `codex/midtrans-pricing`: three lifetime successful free new pictures/account, then IDR9,900 before each new generation. Corrections to an existing root, greetings, full-quality original downloads and padded exports stay free. No branded watermark. Public product, policy and contact pages and same-site Core QRIS checkout are implemented. New checkout defaults to paused.

The [implementation plan](superpowers/plans/2026-10-10-midtrans-website-requirements.md) preserves its planning baseline; this report and the [release checklist](midtrans-review-checklist.md) record subsequent execution. Attachments were source requirements, not assistant instructions or adopted sample policy promises.

## Final local checks

| Check | Result |
|---|---|
| Full Django/PostgreSQL suite | 175/175 passed; six concurrency tests run. |
| Full Django/SQLite suite | 175 run, 169 passed, six PostgreSQL-only skips. |
| General Playwright desktop/mobile | 60/60 passed. |
| Separate fake-payment Playwright desktop/mobile | 4/4 passed, including explicit mocked QR presentation and partial-refund display. |
| Archived Node prototype tests | 4/4 passed; prototype unchanged. |
| Schema drift / whitespace | No changes detected / clean. |
| Synthetic production settings check | `check --deploy`: no issues; no deployment performed. |

Backend commands used disposable PostgreSQL on loopback port 55436 or isolated SQLite and private media. Browser servers used their own databases/media on 8765/8767 and 8775/8777, with separate artifact folders. No customer database or media was modified. Master downloads were compared by hash and dimensions; clean generated/greeting images and mobile QR/desktop paid-order screenshots were visually inspected. Synthetic images do not establish likeness or real AI quality.

## Final review and fixes

A fresh read-only gpt-6-astra reviewer examined the whole branch from `44706b4` to `ba2386d`. It found eight Important issues and one initially Minor audit issue. Audit attribution was re-graded Important because access/privacy changes need durable actor/reason evidence. All nine entered one regression-driven fix pass; no implementer agents or second review were used.

| Finding | Verified fix |
|---|---|
| Refunded historical correction regained root access | Audit and all download paths honor refunded/revoked lineage evidence. |
| Second late historical receipt collided with uniqueness | Migration preserves verified receipts; second payment opens one resolution without duplicate delivery. Returning the extra payment preserves original funded access. |
| Revoked historical purchase silently reported delivery | Revocation stays enforced; unavailable payment opens refund/support resolution. |
| Partial refund stayed pending or invisible | Verified returned/remaining amounts are tracked and displayed, unfulfilled dispatch is held, and further refunds cannot exceed the remaining obligation. Obsolete full requests require reconciliation. |
| Charge timeout lost QR instructions | Pending lookup recovers validated opaque actions or the documented transaction-specific QR endpoint, using the same order/transaction. |
| Paid deletion bypassed resolution | Undelivered paid generation retains one actionable failure/refund/support record. No transfer is submitted. |
| Correction extended retention | New corrections/media inherit root expiry; maintenance also expires legacy derivatives at root deadline. |
| Quarantined files never expired | Quarantined retained files are physically purged at expiry without restoration. |
| Historical changes lacked attribution | Quota initialization, new grant and quarantine record actor, reason and decision independently of preview changes. |

Tests reproduced each reported failure before its fix; the final complete PostgreSQL/SQLite suites passed. Additional regressions protect app-owned refund/duplicate metadata against provider overwrite, original funding after extra-payment refund, invalid partial amounts and full-refund completion after earlier partial returns. No unresolved Important/Critical finding or deferred minor remains. This reports author-tested fixes after the fresh review, not a second reviewer approval.

## Decisions and their costs

The exhaustive chronological execution rulings are preserved below. They include decisions deliberately left as external release gates by the reviewer.

- Ruling: reuse the current clean checkout on a new codex branch — higher-priority workspace guidance prefers the current checkout and reversible authorized work proceeds without another confirmation — risk: files are visible in the primary workspace until reviewed.
- Ruling: unknown legal identity, hours, refund deadlines and merchant activation remain explicit release gates; local pages describe available workflow without inventing promises — risk: owner must finalize these before live activation.
- Task 2: Ruling: add Offer.purchase_unit to distinguish immutable generation offers from retained download offers — selecting by price/name would risk billing old drafts with the wrong offer — cost: one additive catalog field/migration.
- Task 2: Ruling: lazy owner-locked trial initialization counts real historical creation results and legacy consumed allowances, rejects incomplete ready histories pending audit — avoids allocating free quota from unknown history — cost: affected legacy owners require audited reconciliation before new creation.
- Task 3: Ruling: keep shared snapshot preparation in admit_job with an internal payment_offer parameter — avoids duplicating consent/revision/source/prompt validation for paid jobs — cost: worker must independently check billing authorization.
- Task 3: Ruling: require three consumed free slots before buying the next picture; merely reserved slots return wait status — matches payment after three pictures and prevents early accidental purchases — cost: a customer cannot buy while their final free picture is unresolved.
- Task 3: Ruling: explicit root entitlement is granted atomically on free completion before download changes — allows corrections to validate their original picture and removes the old master paywall safely — cost: historical grant migration still required.
- Task 4: Ruling: Refund.requested_by is nullable for automatically raised failure/refund resolution — do not falsely attribute a system request to the customer or invent a staff actor — cost: one nullable field migration, system audit events have no user actor.
- Task 4: Ruling: after a confirmed provider 404 an explicit refresh may retry the charge with the same merchant reference; concurrent creating attempts are fenced for 30 seconds — avoids a second charge identity while recovering crashes — cost: depends on Midtrans's unique order reference behavior, real sandbox validation remains a release gate.
- Task 4: Ruling: terminal statuses confirmed by the provider stop background polling; local cancellations/expiries remain reconcilable, and all later signed webhooks remain accepted — bounds stale payment work while retaining late settlement resolution — cost: a provider changing a confirmed terminal state without notifying would need operational reconciliation.
- Task 4: Ruling: keep Core QRIS on-site display and use only the environment's exact Midtrans image origin; no Snap/redirect/payment-method expansion — smallest flow matching website requirement — cost: one-phone wallet/real QRIS behavior still needs merchant/device validation.
- Task 5: Ruling: historical reconciliation is a dry-run management command with explicit staff/reason for --apply and refusal while legacy jobs/payments are in flight — keeps cutover reviewable without touching customer data here — cost: operator must drain and audit before applying production history.
- Task 5: Ruling: count retained creation records independently of jobs and add orphan consumed legacy allowances; incomplete or active legacy history blocks new creation while session/history remain usable — deleted/expired pictures remain counted and unknown history is not guessed — cost: incomplete cohorts require operator resolution.
- Task 5: Ruling: clean preview replacement reuses atomic private storage and preserves master bytes/hash; missing or changed masters are quarantined and sent to support — never reconstruct deleted files or remove a flattened watermark — cost: unavailable legacy files need support resolution.
- Task 6: Ruling: implement the isolated fake-payment browser harness early to prove the checkout UI RED→GREEN — Task 7 will broaden the same harness rather than duplicate it — cost: task boundaries overlap, release gates unchanged.
- Task 6: Ruling: the staff admin records external refund evidence through the existing MFA/re-auth middleware and AuditEvent instead of adding a money-transfer API — owner approved dashboard/manual procedure remains authoritative — cost: staff must issue and verify the transfer outside the application.
- Task 7: Ruling: new checkout remains paused and the public domain/contact, merchant QRIS/refund and real AI/privacy/quality/economics/infrastructure checks remain external release gates — local synthetic tests cannot establish these facts and no deployment/live charge was authorized — cost: owner/operator must provide real evidence before activation.
- Final: Ruling: real merchant approval, wallet scanning and live refunds remain outside local acceptance — disposable tests cannot establish external channel behavior and no live transaction is authorized — cost: operator must complete sandbox/device/refund evidence before activation.
- Final: Ruling: final legal identity, policy deadlines and support staffing remain owner release gates — local code must not invent business commitments — cost: public paid launch waits for those decisions and monitored support.
- Final: Ruling: real AI quality, economics and processor privacy/deletion remain external evidence gates — synthetic fixtures demonstrate workflow rather than likeness, margin or provider compliance — cost: real processing cannot launch until verified.
- Final: Ruling: customer migration, deployment and infrastructure remain separate release work — authorized local tests use disposable databases/media — cost: backed-up cutover and operational smoke checks remain required.
- Final: Ruling: exclude paid receipts from the legacy active-order uniqueness constraint, retain pending-order uniqueness and one root grant — verified late money must be recorded even when another receipt funds the same picture — cost: do not reverse this schema change over duplicate verified receipts; duplicate fulfillment must stay blocked.
- Final: Ruling: an observed partial refund opens manual resolution, preserves delivered access and bounds further refunds to the remaining amount — the application does not offer partial refunds or submit transfers, but cannot ignore money already returned — cost: staff must reconcile obsolete full requests and verify the cumulative provider report.
- Final: Ruling: refunding a verified extra duplicate payment preserves the original funded picture; refunding its original payment ends access — the extra receipt never funded a second delivery, so revoking the original picture would penalize the customer — cost: the app-owned duplicate linkage must remain protected from provider payload overwrite; regression tests cover this boundary.
- Final: Ruling: preserve the completed local codex/midtrans-pricing branch without merging or pushing — the authorized goal is local implementation/testing and integration was not requested; higher-priority guidance avoids adding an approval flow for unrelated actions — cost: integration and production activation remain a later user decision.

## Limits and release work

No real Midtrans charge/refund, physical wallet scan, real AI generation, production deployment or customer-history cutover was performed. Public momenria.id reachability could not be verified from this machine's DNS. Legal operator/address, usage/tax policy, support hours, refund deadlines/manual remedy ownership, actual merchant/channel approval and existing AI/privacy/quality/economics/security/email/backup/infrastructure evidence remain release gates. Follow the dry-run, backed-up cutover and rollback steps in [operations](operations.md); keep reconciliation available with money in flight. No subscriptions, credit wallet, carts, extra payment methods, new support system or refund-transfer API was added.
