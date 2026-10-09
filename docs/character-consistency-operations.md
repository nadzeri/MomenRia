# Character references: implementation and evaluation

Date: 26 September 2026

Status: application implementation available for isolated validation. No production rollout or live likeness improvement claimed. See [design and quality gates](character-consistency-plan.md).

Requirement-by-requirement evidence and remaining work: [completion audit](character-consistency-completion-audit.md).

## Delivered behavior

New character-enabled template versions freeze the rendered prompt, original-to-slot mapping, actual image attachment order, scene, wardrobe, model, route, recipe digest, exclusions and output settings at admission. Result provenance retains these fields. Legacy versions and jobs keep their existing behavior.

Each assigned original can have a private 1536×1024 source layout containing the original and a face/hair crop. This uses existing pixels and no AI allowance. Original photos remain the identity authority. Generated 2×2 sheets are optional, use only their original as input, carry estimated-view provenance, and require explicit approval before assignment. Rejection retains the source layout. Each source-content/recipe permits two preparation attempts across an account; daily and endpoint limits also apply. Failed attempts count toward this conservative bound. There are no hidden regeneration calls.

Preparation jobs use the existing queue, leases and budget, but no portrait allowance and no result version. All real calls retain their conservative cost reservation until actual cost is reconciled, including rejected or technically unusable output. Unknown dispatch outcomes remain uncertain and are never automatically retried. Cancelled jobs stay cancelled when late responses arrive; unresolved cost still needs reconciliation.

Source replacement invalidates the old sheet. Undo restores eligible matching references. Completed sheet preparation permits a draft template change; assignments are cleared while originals and sheets remain available. Selection and portrait admission enforce the current template's allowed reference strategy, so generated references cannot bypass a source-only rollout.

Result review offers an original-versus-face comparison and per-face feedback. Correction keeps the parent, targets one slot, and inherits other references. Prompt-only correction is not pixel-preserving; reviewers must check non-target people and scene. Old results remain immutable and available while eligible.

## Prepare new versions

Run migrations before starting new application/worker images. New `characters` private volume must be writable by web, worker and maintenance; updated Compose configuration provides it. Existing published templates are never edited by the preparation command.

```bash
.venv/bin/python manage.py prepare_character_templates \
  --model cx/gpt-5.5-image --gateway-path /images/generations \
  --portrait-max-cost-idr 1500 --reference-max-images 9
```

Cost values above are command examples, not verified provider prices. Replace them with conservative measured bounds before any real call. The default prepares source-layout drafts. Add `--generated-sheets --sheet-max-cost-idr <bound>` to prepare an experimental optional-generated configuration. `--slug lebaran` limits changes to one existing template. Repeating identical options is idempotent. Unknown slugs create no versions; inspect command output.

`--test-publish` works only in `APP_ENV=test`. Never use a synthetic test publication as quality approval. Preparing drafts does not activate them in the user's running catalog.

For production publication, first record the deployed gateway contract as a versioned private report. On the still-draft candidate, set `capability_verified=true` and `capability_version` to its report identifier, then recompute `configuration_hash` as SHA-256 of `json.dumps(generation_config, sort_keys=True, separators=(",", ":"))`. Keep the current `processing.prompts.recipe_digest()` in configuration. Evaluate that exact configuration, then attach matching approved `BenchmarkEvidence`. Production publication and admission reject stale recipe/configuration hashes and unverified contracts. A boolean flag alone does not constitute measured capability evidence.

Approval must cover actual route/model, reference order and image limit, output settings, scene policy and sheet strategy. Template changes after evaluation need a new configuration identity and fresh matching evidence. Draft promotion is an operator action; no command auto-approves quality.

## Gateway evidence collected

Read-only discovery of the configured local 9Router `/models/image` endpoint succeeded on 26 September 2026. It advertised the configured `cx/gpt-5.5-image` alias. This proves discovery only. Underlying model identity, reference influence, nine-input support, resizing, edit preservation, cost, timing and data handling remain unverified on this deployment.

Current request uses `model`, `prompt`, `n=1`, `size`, `response_format=b64_json`, and the ordered `images` array. Exclusions are included in prompt prose. No dedicated negative-prompt field, fidelity control, seed, mask or provider-specific feature is assumed. The reported model may be only an alias if the gateway does not return an underlying identifier.

Before opening a real pilot, retain evidence for one through four people, reordered distinct references, nine attachments, response dimensions, request/response limits, timeouts and status lookup. Test correction separately. Do not use template-face crops as evidence that references influence identity; those are suitable only for synthetic lifecycle tests.

## Controlled A–E evaluation

Use an isolated, access-controlled staging database and private media store. Candidates cannot be benchmarked as production drafts through normal admission: production publication already requires approved evidence. In staging use `APP_ENV=test`, `PUBLIC_ACCESS=false`, `AI_GATEWAY_MODE=9router`, explicit admission/budget controls, verified pilot accounts and a worker. Staging test publication enables execution only; it is not permission to publish a quality claim. Never point staging at production database or media.

Get consent for every original, including appropriate guardian authority where applicable. Use a separate project per case to keep evidence distinct; cases can share a pilot account. Portrait creation and correction no longer have usage-count quotas. Keep the experiment bounded by its explicit call and spending caps. Use matching original bytes in the same person/slot order across arms. Store opaque identity-set labels, not names or appearance descriptions, in the manifest.

Prepare each needed template arm in staging with `--benchmark-arm A|B|C|D|E --test-publish`, fixed model/path/output/cost options, and optional `--slug`. Record the resulting template ID before creating the next version. Old published IDs remain usable for exact-version projects even though the public catalog shows only the latest published version. Arm E needs a positive sheet cost bound. Review and approve its generated sheets before portrait admission; preparation is an explicit UI step and included in evaluation accounting.

| Arm | Configuration |
|---|---|
| A | Original references and legacy prompt |
| B | Originals and explicit identity/scene mapping, exclusion block disabled |
| C | B plus exclusion block |
| D | C plus original-pixel layouts |
| E | C plus approved generated sheets and original photos |

Example private manifest, replacing project UUIDs with real staged projects:

```json
{
  "schema": 1,
  "gateway_version": "deployed-gateway-build-and-contract-report-id",
  "cases": [
    {"id": "set01-scene01-D-r1", "project_id": "00000000-0000-0000-0000-000000000001", "identity_set": "set01", "scene": "scene01", "repeat": 1, "arm": "D"}
  ]
}
```

Add matched arms and repeats as planned. The command supports up to 240 cases, validates identical source hashes, geometry, template asset, route and output size within each matched set/scene/repeat, and randomizes queue order deterministically. `--seed` changes scheduling order only; no generation seed is sent.

```bash
# Read-only plan/report; no queued work or provider calls.
.venv/bin/python manage.py evaluate_characters /private/evaluation.json > /private/report.json

# Example bounds only: choose approved limits after inspecting the report.
.venv/bin/python manage.py evaluate_characters /private/evaluation.json \
  --enqueue --max-calls 10 --max-cost-idr 10000 > /private/queued.json

# Run existing worker; repeated command invocation does not enqueue a second copy.
.venv/bin/python manage.py runworker
```

`--enqueue` uses normal admission atomically. An invalid case, active job, unavailable variant or daily budget failure rolls back new admissions. The manifest digest and case ID form stable idempotency keys. Do not edit a manifest to retry an uncertain call. Reconcile the existing attempt first. Preparation/correction jobs in the listed projects count toward the plan's call and cost bounds. The bound on this command covers portrait scheduling; explicit preparation before it still needs its own admission budget. Missing actual costs remain conservative estimates, not zero.

Run the same read-only command after jobs and feedback finish. Reports include per-face acceptance with all intended faces in the denominator, missing per-face/whole-portrait feedback, technical/uncertain failures, wrong-person reports, requested/reported models, result latency, sheet rejection count, known-or-bounded spend and cost per accepted portrait. Whole-portrait votes never manufacture per-face votes. Treat synthetic outputs as workflow evidence only.

For blinded review, an operator presents each randomized result with original references through owner-authorized private access, withholding arm labels and configuration. The JSON report is operator-facing and is not a blinded participant interface. Collect exact-slot votes through the comparison UI, whole-portrait votes separately, and a private supplemental review table for template adherence, sample-face leakage, swaps, non-target correction changes, subgroup counts and uncertainty intervals. Record all cases, failures and missing feedback. No biometric database or automatic likeness score is introduced.

The small engineering screen is not population validation. Check the predeclared gates in the design plan: absolute and baseline-relative acceptance, zero observed swaps/sample identities, template/correction preservation, subgroup uncertainty and bounded cost/latency. Promote E only when its measured gain over D warrants added calls, delay and review. The command never changes `BenchmarkEvidence.approved`.

## Retention, failure and rollback

Sheets inherit original expiry and are inaccessible after original consent/availability ends or project deletion. Maintenance includes character sheets in expiry, physical deletion and orphan sweep. Back up source, character and result volumes together with matching database/hash manifests and separate deletion tombstones. Restore into isolation, replay tombstones/expiry and verify sheet/source associations and hashes before exposing any media. Do not restore a sheet after its source's expiry.

Pause a failed new template version to return new catalog choices to the previous published version. Existing projects retain their selected version; admission rejects paused variants while results/downloads remain available. Queued jobs retain their frozen inputs. Preserve uncertain-job reconciliation and budget reservations during rollback. Schema rollback requires no outstanding preparation jobs and an explicit migration review; application-only rollback must remain schema-compatible.

Local storage files written inside a rolled-back database transaction may remain unreferenced until the existing one-hour orphan sweep. They are never served without an eligible database record. Temporary/private media must not be copied into public static directories or committed alongside the plan.

## Validation and remaining release gates

Runnable verification uses the repository's Django tests, PostgreSQL concurrency cases, Node checks and Playwright desktop/mobile journeys. Current execution logs and review rulings are kept in `.superpowers/sdd/character-consistency-plan/progress.md`.

Still required before rollout: consented likeness data, agreed spending cap, live gateway capability probes, actual owner/independent review, subgroup and correction evidence, provider eligibility/retention confirmation, and an exact matching benchmark approval. None follows from green synthetic tests. Video, genuine multi-photo identity grouping, cross-project libraries and automated biometric scoring remain later scope.
