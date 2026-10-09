# Character consistency completion audit

26 September 2026. Objective: implement `character-consistency-plan.md`, including its evidence gates. **Not fully complete:** implementation and local verification exist; live capability, likeness and rollout evidence does not.

Previous goal turn classified as **progress**: application code, docs, review fixes and verified test evidence changed. This audit turn adds direct regression coverage and maps remaining requirements without reducing scope.

## Requirements and evidence

| Requirement | Current authoritative evidence | Assessment |
|---|---|---|
| Original remains primary identity authority; sheets never replace it | `processing/prompts.py` identity instructions; `processing/services.py` source snapshots; `processing/worker.py::_gateway_images`; generated-sheet original-only input test | Implemented and locally verified |
| Two-panel original/crop layout; bounded dimensions; aspect ratio; no synthesized source pixels | `projects/character_sheets.py::build_source_sheet` uses Pillow crop/contain, local labels and neutral background; cached/private source-sheet test; edge-crop regression | Implemented; deterministic construction and bounds verified |
| AI front/close-up/three-quarter/profile sheet; estimated unseen geometry; approval against original | Versioned `SHEET_PROMPT`, original-only preparation, panel provenance, Indonesian review dialog; browser rejection/retry/approval journey | Workflow verified; real generated panel fidelity remains unverified |
| Back/outfit views, extra expressions, genuine multi-photo groups | Plan explicitly limits first implementation to one original and simple 2×2 sheet | Later scope, not silently substituted |
| Template controls scene/wardrobe; originals control faces/hair/head covering | Frozen template scene and wardrobe policy plus identity instructions; prompt admission test | Implemented; real adherence needs live review |
| Explicit person/slot/image-role mapping, image-left coordinates, one to four people, nine references | One-through-four mapping test, non-left-to-right slot positions and actual nine-attachment content-hash test | Locally verified; provider influence/capacity still unverified |
| Respect input limit and reference ordering; never silently drop a person | `freeze_portrait_prompt` cap/reordering; `_gateway_images` consumes same manifest; limit and identity-first attachment tests | Locally verified; chosen provider limit remains a measured release gate |
| Freeze rendered prompt, exclusions, model/path, source/sheet hashes, scene and recipe | Admission snapshot and result generation provenance; worker returns saved prompt; environment/config drift test | Implemented and locally verified |
| Stage-specific exclusions; do not blindly preserve source outfit/background | Creation vs correction instruction blocks; separate stored exclusion block, no unsupported provider fields | Implemented; impact on likeness still unmeasured |
| Correction targets one person and retains parent/other source references | Correction replacement/provenance test and existing paid-file/shared-allowance regression | Data and prompt behavior verified; no proof yet that real model preserves non-target identities/pixels |
| Model/edit route pinning and verified capability-dependent controls | New template config pins creation and optional edit model/path; production configuration gate test | Implemented; edit route and processor contract need live evidence |
| One versioned CharacterSheet model, private bytes, immutable input/output, project/source association | Projects migrations 0006/0007, model save guard, shared eligibility; PostgreSQL immutable-trigger test | Implemented and database-verified |
| Within-project reuse, new artifact for replacement/recipe, assignment undo and template changes | Source-sheet cache, snapshots, matching-sheet undo test, source replacement correction test, completed-preparation template-change test | Locally verified |
| Generated artifact cannot bypass source-only rollout | Shared `eligible_sheet` strategy gate and UI filter; bypass regression | Verified; reviewer finding fixed |
| Narrow API operations; owned sources, expected revision, idempotency and no arbitrary provider payload | `projects/api.py`, `processing/api.py`, routes, `openapi.yaml`; generated/idempotency/private-preview tests; review owner/stale/replaced-source regression | Implemented and locally verified |
| Keyboard/focus/status/mobile UI; Indonesian labels; per-face comparison/feedback | Existing dialog/focus helpers retained; real desktop/mobile browser journeys, wrong-person feedback and overflow checks; screenshot inspection | Browser-verified; physical device/provider quality not implied |
| No AI call/portrait allowance for local layouts | Local Pillow builder and source-assignment path | Verified by implementation and local flow tests |
| Generated preparation uses durable job/lease/budget, no result/creation grant | Job operation/constraint and migration, admission, worker finalizer; generated-sheet allowance test | Implemented and database/browser-verified |
| One active project job; bounded explicit retry and account limits | Shared active-job constraint, generated admission two-attempt and daily limits; rejection/retry test and existing concurrent admission tests | Locally verified; no automatic retry of unknown execution |
| Count preparation, rejected output, billed failures, uncertain calls and corrections | Shared budget reservation/reconciliation, provider-completed marker, conservative unknown costs, evaluation project-wide accounting; cost/late completion/uncertainty tests | Local accounting verified; real invoices/cost ceilings not yet measured |
| Late completion/deletion and stale workers cannot publish or revive data | Deletion epoch, source eligibility, fencing and terminal-state guards; late timeout/completion, stale-claim and maintenance-race tests | Locally verified; reviewer race fixed |
| Source consent/expiry and sheet hashes rechecked before dispatch/publication | Worker eligibility plus source/sheet file hash checks; expiry/private preview/deletion tests | Implemented and locally verified |
| Sheets expire with original; delete tracked and orphan media; backup/tombstone procedure includes sheets | Maintenance handles characters, source expiry/consent and physical deletion; Compose volume; operations/runbook restore instructions | Application cleanup verified; actual off-host backup/restore and provider deletion drill not performed |
| New immutable template versions and matching configuration/evidence gates | `prepare_character_templates`, `TemplateVersion.clean`, matching BenchmarkEvidence requirement, production recipe/config gate; catalog regression | Implemented; no customer catalog versions promoted |
| Baseline + A–E controlled experiment and bounded execution | `evaluate_characters` dry-run/enqueue/report, normal admission/idempotency/budget checks; command regression; staging runbook | Tooling verified, experiment not run |
| Matched identities/scenes/output/routes, randomized ordering, seeds only if supported | Manifest comparison and deterministic scheduling seed; no unsupported generation seed | Implemented; consented case manifest not provided |
| Blinded owner/independent review and richer quality metrics | Per-face owner UI and separate whole-portrait votes; private report and documented operator-blinded procedure/supplemental table | Collection mechanism exists; reviews, subgroup analysis, sample-face/swap/correction evidence absent |
| Missing feedback and failures stay in denominators | Report counts all planned faces, exact-slot votes only, failures and missing responses; command regression | Verified; reviewer metric issue fixed |
| At least 90% acceptance and baseline-relative gain; zero observed swaps/sample identities; no scene/correction regression | Requires consented matched live results and recorded owner reviews | Not proven; mandatory release gate |
| E default only if measured gain justifies delay/cost/review burden | Optional generated strategy and source-only selection guard; manual promotion gate | Enforced as an experiment; comparison not measured |
| Passing 1–2-person variants first, then validated 3–4; bounded latency/spend; rollback | Draft preparation, publication controls, latest-published catalog behavior and rollback runbook | Software controls delivered; live pilot/rollback drill not executed |
| Existing queued jobs/results/downloads retain legacy/frozen behavior | Legacy worker fallback plus existing result, ownership, correction and immutable-media tests | Locally verified |
| Video integration, video billing and global character library | Explicitly excluded from initial plan | Remain outside current implementation |
| Claims match evidence; no exact-identity promise | UI synthetic/estimated-view disclosures and runbook quality gates | Implemented; no likeness success claim made |

## Verification inspected

- Full PostgreSQL 18 execution: **82 passed**, no skips (`.superpowers/sdd/character-consistency-plan/postgres.log`). Includes database constraints and concurrent admission/budget tests.
- Full browser execution: **30 passed**, desktop Chromium and mobile WebKit (`browser-full.log`). Real Django APIs and fake provider; not a likeness benchmark.
- SQLite checkpoint: **81 discovered, 79 passed, 2 PostgreSQL-only skips**; four final changed lifecycle cases passed separately.
- Audit regression addition: edge-clamped source crops; other-owner, stale-revision and replaced-source review rejection (`completion-audit-tests.log`). These supplement, rather than retroactively change, the recorded full-suite count.
- Four Node checks passed; no migration drift; Compose configuration validated; OpenAPI YAML parsed and all internal references resolved.
- Independent final review: no Critical findings; three Important issues fixed and covered. No deferred Minor findings.

## Required next evidence

Missing input is unchanged: identify an authorized, consented live reference set/pilot projects and total spending cap in IDR. Current synthetic test fixtures cannot establish real-person likeness. No paid provider calls, production migrations, rollout or customer-data reuse are inferred from those fixtures.

Once supplied: stage approved references privately; verify actual gateway contract and cost within the cap; run bounded matched arms; obtain owner and independent review where practical; report uncertainty and all failure/missing-feedback denominators; approve only exact passing configurations; perform limited rollout and documented operational checks. Until those results exist, the full goal remains unachieved.

No background generation or evaluation is currently running. This is an input-dependent block, not a verified wait on a live process. The same missing-input condition was revalidated across three consecutive goal turns. Goal is now **blocked**, not complete; resume when the required live-evaluation inputs arrive.
