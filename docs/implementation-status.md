# MomenRia implementation status

Status date: 2026-09-25. `Implemented` means code and local/container evidence exist. It does not mean production release is approved. Current scope excludes payments; see `docs/launch-readiness.md`.

## Technical requirements

| Requirement | Status | Evidence or remaining gate |
|---|---|---|
| TR01 | Partial | Full workflow implemented; public release still needs provider, benchmark, policy, and production evidence below. |
| TR02 | Implemented | One Django codebase; separate web, worker, maintenance, migration, database, and proxy services. |
| TR03 | Partial | Immutable container and environment guards exist; D01 production host/domain remains unprovisioned. |
| TR04 | Implemented | UUIDs, UTC data, integer rupiah, decimal cost records, foreign keys, checks, and immutable-record triggers. |
| TR05 | Implemented | Private accounts by default; production rejects shared-owner mode. Signup, verification, login and account pages work with the email-only user model. Test-only shared demos remain explicit. |
| TR06 | Implemented | Immutable versioned templates, stable normalized slots, local YuNet detector, retained MIT notice/hash. |
| TR07 | Implemented | Streamed temporary upload, decoded-byte/MIME/size/pixel/face checks, consent, private atomic storage. |
| TR08 | Implemented | Admission validates ownership, consent, sources, variant, offer, budget, queue, storage, and freezes inputs. |
| TR09 | Implemented | PostgreSQL `select_for_update(skip_locked=True)`, committed lease, heartbeat, fencing, and uncertain state. |
| TR10 | Implemented | Updated 26 September 2026: unlimited creation and correction counts. New jobs need no allowance; legacy allowance records stay intact for history. Per-project concurrency and global resource controls remain. |
| TR11 | Partial | Real 9Router adapter authenticated against `cx/gpt-5.5-image`; it sends frozen model/path, template or parent master, ordered references, bounded base64 responses, request identity, and conservative uncertain states. Cost and retry contract still need provider evidence. |
| TR12 | Partial | Atomic full master then derived preview, hashes, dimensions, expected face-count gate, quarantine states, and disclosed 1448-to-2048 finishing path exist. Likeness/mapping quality still needs D07 benchmark output. |
| TR13 | Implemented | Each result stores exact source/region snapshot; expired references remain labeled, not silently extended. |
| TR14 | Implemented | Local deterministic greeting versions, 48-code-point/control/width checks, inherited expiry, separate hashes. |
| TR15 | Blocked by D04 | Signed Midtrans notification/status validation exists. Real QRIS charge creation stays disabled pending merchant contract. |
| TR16 | Implemented | Entitlement binds owner, order, result ID, and master hash; repeated exact-version download until expiry. |
| TR17 | Partial | Idempotent refund record/reconciliation state exists; provider submission needs D04/D11 procedure. |
| TR18 | Implemented with test-only exception | Versioned same-origin API, CSRF, schema/body checks and owner scoping. Shared-owner demo mode is rejected in production. |
| TR19 | Implemented | Access-time expiry plus five-minute source/result/grant/order/deletion/orphan sweep. |
| TR20 | Blocked by D10 | Backup/restore/tombstone runbook and stale-backup alert exist; independent destination and restore drill remain. |
| TR21 | Implemented | Atomic global budget window, worst-case retry reserve, queue/concurrency/storage bounds, audited admission switch. |
| TR22 | Implemented | Stable analytics IDs, allowlisted client event, server financial/job events, local transactional outbox delivery. |
| TR23 | Blocked by D01/D12 | Health/alert controls exist; production load, mobile-network, latency, and capacity measurements remain. |
| TR24 | Partial | Security headers, admin MFA/re-auth, password validators, rate limits, private media, production shared-owner rejection and ownership tests exist. Real production infrastructure and identity evidence remain release gates. |

## Acceptance evidence

Automated evidence currently covers 55 Django cases on PostgreSQL: public shared-owner access, stale customer-login bypass, admin-login preservation, passwordless public deletion, upload validation and canonical upload idempotency, strict multipart/JSON mutation schemas, ownership, permanent template/offer/result immutability, assignment undo, generation idempotency, real 9Router request/response and correction contracts, request-ID-preserving uncertainty, provider-dimension diagnostics, output face-count rejection, disclosed provider-output finishing, explicit test-only unbounded admission, correction lineage/allowance/source expiry, crash rollback/orphan cleanup, lease recovery/uncertainty, deletion during queue, greetings, strict payment identity/refresh/replay/atomicity, live and unavailable late settlement, refund idempotency/schema, staff MFA grant claiming/audit, and admission/budget races. Original prototype suites also pass. The new browser suite covers desktop Chromium and mobile WebKit, including the actual Django workflow and targeted simulated recovery cases. See `docs/launch-readiness.md` for exact evidence. Remaining release acceptance (payment cases apply only to a later paid release):

- AT06: repeat crash injection with host power/process loss against the selected production storage. Deterministic post-write/pre-commit rollback, uncertainty, and orphan cleanup pass.
- AT07: run the correction lineage and unchanged-paid-file checks with the approved targeted-edit gateway. Local state/allowance behavior passes.
- AT08 and AT10: run real two-, three-, and four-person gateway/output contract and likeness benchmark.
- AT11 to AT13: deliver actual sandbox callback, reordered/late/duplicate cases against selected merchant. Deterministic signed callback, replay, mismatch, and late-settlement cases pass.
- AT16: expand deletion race injection through upload, dispatch, correction, finalization, and payment callbacks.
- AT17: perform timed restore drill against D10 backup destination plus tombstone replay.
- AT18: test phone sleep, slow upload, wallet redirect, keyboard, screen reader, and enlarged text on target devices.
- AT19: exercise staff MFA/re-auth and role matrix with production identity setup.
- AT20: validate funnel/cost metrics against pilot fixtures and missing-feedback denominator.
- AT21: repeat isolation checks on separate production host before admission.

Admissions, real AI dispatch, and real payment creation remain disabled by default. Existing synthetic output is visibly marked and cannot be purchased.
