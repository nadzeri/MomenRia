> Historical scope/evidence. Pricing, quota, watermark and payment policies are superseded by [the October Midtrans/pricing plan](superpowers/plans/2026-10-10-midtrans-website-requirements.md).

# MomenRia competitive review

26 September 2026. Scope: private family portraits made from separate photographs, with Indonesian families as the primary audience.

**Decision: improve upload, discovery, review, and sharing now. Overall competitive superiority is not established.** Competitor facts below are public product claims, not independently measured results. No competitor account, paid generation, or customer photograph was used in this review.

## Comparison

| Customer need | MomenRia at inspection | Public competitor baseline | Result of this change |
|---|---|---|---|
| Find a suitable scene | 28 catalog concepts across six collections, including eight Indonesian university settings; global search returned collection cards even for one exact template | Family Photo Maker advertises 50+ styles and occasion collections. [Product page](https://www.familyphotomaker.com/) | Search and people filters now display matching templates directly. Clearing filters restores collections. Catalog breadth remains behind the advertised baseline. |
| Bring multiple people together | 1–4 people; a separate upload dialog and consent checkbox for each face | CreateVision presents 2–5 individual photo inputs; BringBack advertises up to eight reference photos and explicit group counts. [CreateVision](https://createvision.ai/ai-family-photo-generator), [BringBack](https://bringback.pro/ai-family-portrait) | One file selection and one consent step can fill the remaining slots. Each photo has a preview and explicit face-position selection. Duplicate positions are rejected before upload. Group capacity is unchanged. |
| Check identity after edits | Per-face source comparison, feedback, targeted corrections, and saved result versions; switching versions required remembering the previous image | BringBack asks users to compare each face with references before downloading. [Workflow](https://bringback.pro/ai-family-portrait) | Two saved versions can now be inspected side by side without changing the selected result. Existing per-face review remains available. An advantage in review controls is plausible; competitor post-login controls were not tested. |
| Prepare photos for sharing | One original-aspect watermarked preview download | BringBack advertises four generation canvas ratios; Family Photo Maker advertises high-resolution downloads. [BringBack](https://bringback.pro/ai-family-portrait), [Family Photo Maker](https://www.familyphotomaker.com/) | Original, square 1:1, portrait 3:4, and Story/Status 9:16 preview downloads. Frames preserve the entire image and watermark without regenerating faces. These are preview exports, not new composition ratios or high-resolution masters. |
| Control private photographs | Owner-only media, consent, seven-day sources and 30-day results by default, project deletion, optional limited support access | BringBack describes account-controlled private results and deletion. [Privacy description](https://bringback.pro/ai-family-portrait) | New export formats use the existing owner and expiry checks. No public share links, new processors, or permanent derivatives are introduced. Neither privacy superiority nor competitor implementation was independently established. |

Indonesian moments, explicit face placement, original-reference review, and repeatable targeted correction form a useful focused proposition. The app's source references and immutable versions already provided much of that behavior before this task. Those existing features are not new work from this review.

## Implemented acceptance criteria

- An exact global query such as `wisuda ui` exposes the matching template immediately.
- Users can choose several photographs once, inspect their mapping, and grant consent before sending anything.
- When a later file fails, earlier assignments stay saved. Retry retains successful progress and upload identities; selecting replacement files targets the remaining slots.
- Comparing versions does not change the selected result or regenerate any image.
- Framed exports keep all image edges, retain the watermark, add no original-image detail, and do not extend retention or create results/jobs.
- Download filenames identify the chosen format. Invalid formats, other owners, expired results, and deleted media are rejected.
- Existing private single-photo upload, correction, greeting, and preview download flows remain usable.

Implementation uses the existing Django endpoints, Pillow, native file inputs/selects, and dialog styling. No package or database migration is added. Free-preview and master-entitlement policies remain intact. An outdated template-detail sentence describing a one-creation limit was corrected to match the existing unlimited-count policy and capacity limits.

## What must still pass before claiming a win

Feature count alone does not answer whether the family still looks like itself. The following comparison remains unrun:

1. Use the same consented portraits across MomenRia and an agreed competitor, with equivalent scene instructions. Include solo, pair, three-person, and four-person cases, with representative ages, skin tones, glasses, and hijab. Reserve an independent holdout set; avoid optimizing repeatedly on the evaluation examples.
2. Randomize output order for owner and independent review. Count every submitted case, including failed generations and missing reviews. Record per-face likeness acceptance, wrong-person/duplicate/missing faces, whole-portrait preference, and regression in untouched faces after a correction.
3. Require at least 90% per-face acceptance, zero observed swaps or surviving sample identities, and no correction regression, following the existing [character consistency gates](character-consistency-operations.md). A small zero-event sample is not a guarantee of safety.
4. Require a statistically supported preference advantage over the named competitor; report the sample size and uncertainty, not only a winning percentage. Record time to first accepted portrait, p50/p95 latency, cost per accepted portrait including retries, and completion rate on real mobile devices.
5. Publish only the exact tested template/model configurations that pass. Larger groups, pets, more styles, and higher-resolution delivery need their own evidence before adding claims.

Inputs still needed: the competitor to use for live tests (default comparison candidate: BringBack), authorized reference files or pilot projects with consent for each destination, and a total test-spending cap in IDR. Existing evaluation tooling can be reused; see [character consistency operations](character-consistency-operations.md). Synthetic fixtures verify software behavior but cannot establish likeness or market superiority.

## Verification

- Backend: 86 tests discovered; 84 passed and two PostgreSQL-only concurrency cases skipped on SQLite. The new export test checks dimensions, preserved image boundaries without upscaling, ownership, expiry, invalid formats, deleted media, master restrictions, and unchanged result history.
- Node: all four existing checks passed.
- Migration check: no changes detected. OpenAPI YAML parses and exposes the four supported preview formats.
- Targeted browser checks: all four passed on desktop Chromium and mobile WebKit, using a disposable Django database and the synthetic worker. They exercise duplicate-position validation, invalid-file recovery, an intentionally lost response after a real assignment, version comparison, and actual framed downloads.
- Visual inspection: desktop and mobile version comparison, mobile Story export, the batch-upload dialog, and direct catalog search. Synthetic screenshots demonstrate UI behavior, not AI likeness.

Full browser regression: **34 passed**, 17 scenarios each in desktop Chromium and mobile WebKit (2.2 minutes). Desktop and mobile now use separate disposable servers/databases on ports 8765 and 8767 so one suite does not exhaust the other's real network rate-limit bucket. Production rate limits were not changed. The existing keyboard test now follows the direct search result instead of the removed collection hop.

Reproduce with `npm run test:e2e`, `.venv/bin/python manage.py test --noinput`, and `node --test test-*.cjs`. Browser screenshots and the HTML report are under `test-results/` and `playwright-report/`. Deployment, customer-data reuse, and paid provider calls are outside the local verification performed in this task.

## Live-evidence audit

A subsequent read-only audit found no benchmark records, generated results, or jobs in the workspace SQLite database. This describes that local database only, not any external deployment. The existing `evaluation.log` records two software tests, not an executed likeness study. The only observed local worker belongs to the disposable synthetic preview server on port 8766; no competitor evaluation process was observed.

The bounded `evaluate_characters` command is available and requires an actual manifest of pre-consented pilot projects. Its A–E report compares MomenRia reference strategies; it does not itself generate competitor outputs or establish a competitive win. No authorized competitor test set or spending cap has been supplied in this task. The requested overall outcome therefore remains incomplete despite passing software checks. Further changes to identity strategy, group size, and output-quality claims should follow measured failures from that comparison.

Goal status: **blocked**, after the same missing-input condition persisted across three consecutive goal turns. The final audit again found zero local benchmark records/results/jobs and no running `evaluate_characters` process. No live experiment is waiting in the background. Resume with authorized reference paths or pilot projects, consent covering the MomenRia provider and the chosen competitor, and a total spending cap in IDR. Then execute the matched comparison, improve measured weaknesses, and repeat verification before claiming superiority.
