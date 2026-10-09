# Assessment A — independent design and UX review

Date: 9 October 2026. Target: the Django-served MomenRia application in `templates/app.html`, `static/app/server.js`, `static/app/server.css`, and branded account templates. Mode: Persuade for the landing page; Operate for catalog, studio, results, support, and account management; Read for guidance and policies.

Assessment A used source inspection and its own fresh browser tab. No detector findings or Assessment B report were read. The parent ran Impeccable context once. This report is an input to the parent synthesis, not the combined audit. It contains no app changes.

## Verdict

**The identity is specific to MomenRia; the working experience needs a substantial hierarchy and flow revision.** Preserve the cream, ink, coral, lilac, and lime palette; expressive Bricolage headings; casual Indonesian voice; and physical-photo composition. The family portraits, Indonesian celebrations, and numbered face placement make the product recognizable. This is not an interchangeable SaaS dashboard.

The visual system is strongest at inviting people to imagine a family portrait. It becomes less effective when the person must upload, compare, correct, and save it. Large promotional spacing survives into working screens, optional controls appear before the primary task, and the most important decision—whether each face is correct—has no durable visible state. A comprehensive revamp should restructure the studio and result journey while preserving the incumbent identity. Replacing the palette or adding more animation would miss the main problem.

**Nielsen score: 24/40 — Acceptable, with significant improvements needed.** This is a qualitative design review, not a usability-study result. No heuristic was marked n/a because the assessed product includes interactive workflows.

## What was actually inspected

The disposable preview was `http://127.0.0.1:8766`. Only the supplied synthetic account and supplied catalog-derived AI face fixtures were used. No existing private account or personal media was inspected.

| Surface or flow | Live coverage in Assessment A | Source coverage |
|---|---|---|
| Landing | Desktop first viewport, DOM of full page | Hero, collections, steps, privacy, FAQ, footer |
| Template catalog | Desktop and 390 × 844 mobile | Global search, person count, collection filtering, empty and missing states |
| Collection | Desktop Hari raya & perayaan, all nine card entries | Shared collection component and six moment groups |
| Template detail | Desktop Lebaran Bersama | Shared detail component, including university disclaimer |
| Studio | Desktop empty and mobile empty/filled | Frozen state, undo, template switch, reusable photos |
| Authentication gate | Live studio → login → same studio | Pending route, verification gate |
| Single upload | Desktop initial dialog | File, consent, size/error handling, saved-source choice |
| Batch upload | Mobile choose/review/save two synthetic fixtures | Duplicate-position and partial-success handling |
| Character reference | Mobile source-reference dialog | Optional generated reference, approve/reject variants |
| Generation | Mobile queued and ready | Other named processing, failure, uncertain, cancelled states |
| Project library | Live empty state | Populated cards, expiry labels, missing project |
| Result | Desktop and mobile synthetic result | Expired sources/results, capabilities, version selection |
| Face comparison and correction | Mobile comparison, negative feedback, correction form and submitted synthetic correction | Feedback handlers and correction payload |
| Greeting | Mobile text entry, saved synthetic new version | Empty greeting removal and length limit |
| Version comparison | Mobile two-image comparison | Version selectors |
| Export | Mobile original and Story preview | Four formats and download links; download file not opened |
| Help / support | Desktop authenticated contextual form and unauthenticated gate | Ticket list, response and revoke-access components; no messages sent |
| Guide, privacy, terms | Desktop visual and DOM | Full copy |
| Account login, email, security overview | Desktop visual | Shared auth layout and custom account templates |
| Password change and logout | DOM; logout completed for synthetic account | Custom templates |
| Signup, verification, reset success/failure, email confirmation | Source only in A; parent covers additional account routes | All project-provided templates |
| Payment/orders | Source only; disabled in this preview | Capability gate and dormant order view |
| Admin / legacy root prototype | Outside Assessment A live coverage | Parent handles separate scope |

Desktop viewport was the browser default, approximately 1265 × 712. Mobile viewport was explicitly 390 × 844 (390 CSS px window width, 375 px document content area with scrollbar). The override was reset. Not every one of the 28 catalog examples was individually evaluated. Simulated generation validates workflow only; it cannot establish real AI quality or latency.

Saved evidence: [desktop studio](/Users/nadzeri/Documents/Upstacker/MomenRia/docs/design-audit-2026-10-09/evidence/a-studio-desktop.jpg), [upload dialog](/Users/nadzeri/Documents/Upstacker/MomenRia/docs/design-audit-2026-10-09/evidence/a-upload-dialog.jpg), [mobile catalog](/Users/nadzeri/Documents/Upstacker/MomenRia/docs/design-audit-2026-10-09/evidence/a-catalog-mobile.jpg), [mobile studio](/Users/nadzeri/Documents/Upstacker/MomenRia/docs/design-audit-2026-10-09/evidence/a-studio-mobile.jpg), [mobile result](/Users/nadzeri/Documents/Upstacker/MomenRia/docs/design-audit-2026-10-09/evidence/a-result-mobile.jpg), [mobile correction](/Users/nadzeri/Documents/Upstacker/MomenRia/docs/design-audit-2026-10-09/evidence/a-correction-mobile.jpg), [desktop result](/Users/nadzeri/Documents/Upstacker/MomenRia/docs/design-audit-2026-10-09/evidence/a-result-desktop.jpg), [account email](/Users/nadzeri/Documents/Upstacker/MomenRia/docs/design-audit-2026-10-09/evidence/a-account-email.jpg).

## Strengths to preserve

1. **The invitation feels warm and local.** Photo prints, Indonesian occasion taxonomy, direct language, and recognizable family imagery reinforce the actual product. The hero has a clear primary action and honestly labels sample AI imagery. [server.js:102](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:102)
2. **The user retains useful control.** Uploaded sources survive template changes; batch upload preserves partial successes; earlier results survive corrections; dialogs have explicit exits; expiry dates are visible; support image access is optional and revocable. These are valuable product decisions, not merely interface polish. [server.js:233](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:233), [server.js:368](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:368), [server.js:303](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:303)
3. **Basic orientation and reassurance are already present.** Active navigation, mobile bottom navigation, numbered face positions, upload counts, saving feedback, queued-state reassurance, free watermark disclosure, and plain-language connection errors give the redesign a sound base. [server.js:79](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:79), [server.js:277](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:277), [server.js:286](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:286)

## Five priority issues

### A1 — P1: Face review loses continuity at the moment accuracy matters most

**Observed:** In the comparison dialog, choosing “Belum mirip” closes the dialog and shows “Masukanmu sudah tersimpan.” The result view does not mark the face as needing work or offer the next correction action there. Opening “Wajah 1” separately produces a correction dialog titled only “Perbaiki satu wajah,” with no selected face number or portrait. It says “Pilih satu wajah” even though that selection has already happened. The optional replacement file is visible while the operation is still “Bikin wajah lebih mirip.”

**Source:** [face comparison, server.js:191](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:191), [correction dialog, server.js:391](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:391), [feedback handler, server.js:512](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:512), [result rendering, server.js:303](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:303).

**Inference:** A user can reasonably think “Belum mirip” starts a repair, forget which face was selected, or return later without knowing which faces they checked. This is particularly costly when family resemblance is the product's promise.

**Recommendation:** Make each face a persistent review item: thumbnail, number, and clear “Belum dicek / Sudah sesuai / Perlu koreksi” state. After negative feedback, offer “Perbaiki wajah 1” in the same context. Keep the selected face thumbnail and number in correction. Only reveal a replacement input when that operation is chosen. Keep the existing warning to recheck other faces after correction. Do not make saving feedback look like successful correction.

**Acceptance:** A user can identify the chosen face, see that feedback was recorded, start its correction, and return to a clearly marked new version without remembering a previous dialog.

### A2 — P1: Mobile working screens make users scroll through context before reaching the task

**Observed:** At 390 × 844, the studio's first viewport ends at the photo preview and tips. Upload controls follow the large preview, then a repeated template thumbnail/title, a full-width “Ganti template” button, explanatory copy, and another heading. On the two-person result, “Download preview” begins at about 1788 CSS px from the document top before extra versions are added. Reference photos and review instructions precede the action panel; the persistent bottom bar provides global navigation rather than the current next action. In the mobile version comparison, each entire group portrait is roughly a small half-width thumbnail, making fine likeness differences hard to assess.

**Source:** [studio, server.js:277](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:277), [result, server.js:303](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:303), [single-column breakpoint, server.css:440](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.css:440), [mobile studio spacing, server.css:516](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.css:516).

**Inference:** The interface asks a distracted phone user to rediscover progress and the next action after each interruption. The repeated template chooser gives a secondary task more prominence than uploading.

**Recommendation:** Give Operate pages a compact header, a concise progress summary, and one contextual bottom action above safe-area navigation: “Tambahkan 2 foto,” “Buat foto,” or “Simpan foto,” according to state. Collapse chosen-template details to a compact summary with a secondary “Ganti” action. Keep preview, face assignments, and submission close together. Keep review available before download without forcing users to traverse every optional tool. On phones, compare one selected face at useful scale, or provide a full-width before/after toggle; keep whole-image comparison as an alternative.

**Acceptance:** On mobile, a first-time user can see the next step without exploratory scrolling, and a returning user can save or resume from the visible state. Desktop should retain its useful large portrait view.

### A3 — P1: Account recovery directs locked-out users to a support form that requires login

**Observed:** Logged-out Bantuan shows FAQs and “Masuk untuk minta bantuan.” The verification-sent and password-reset-done templates tell a user whose email has not arrived to contact that Bantuan page. The project config requires email verification. There is no public contact route in the inspected help interface.

**Source:** [support gate, server.js:316](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:316), [verification_sent.html:12](/Users/nadzeri/Documents/Upstacker/MomenRia/templates/account/verification_sent.html:12), [password_reset_done.html:16](/Users/nadzeri/Documents/Upstacker/MomenRia/templates/account/password_reset_done.html:16), [mandatory verification, settings.py:144](/Users/nadzeri/Documents/Upstacker/MomenRia/momenria/settings.py:144).

**Inference:** A person unable to receive verification or reset mail is directed toward a route that assumes account access. The exact mail-delivery failure was not simulated; the recovery dependency is visible in the UI and source.

**Recommendation:** Add an explicitly scoped public “Tidak bisa masuk?” support route for account access problems, retaining private project tickets for authenticated users. Verification and reset status pages should show the destination email where appropriate, resend/correction choices with cooldown feedback, and a working contact path. Show a real response expectation only if operations can support it.

**Acceptance:** A user who cannot log in can request account help without first resolving the issue they need help with.

### A4 — P1: Privacy copy and the invitation to upload describe different launch states

**Observed:** Landing and auth copy say “Fotomu pribadi” and invite users to upload family photos. The privacy page says the provider, retention, and deletion details must still be established before accepting public customer photos, and “Untuk sekarang, jangan pakai foto pribadi di demo.” That paragraph renders even when the shared-demo banner is absent, as in the authenticated synthetic preview. Terms also say public service terms and operator details must be ratified before public launch.

**Source:** [landing privacy invitation, server.js:130](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:130), [privacy, server.js:310](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:310), [terms, server.js:313](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.js:313), [auth reassurance, base.html:31](/Users/nadzeri/Documents/Upstacker/MomenRia/templates/allauth/layouts/base.html:31).

**Inference:** A cautious parent cannot confidently tell whether the current account-based service is ready for personal photos. This is a product-trust contradiction, not a claim that the implementation leaks images.

**Recommendation:** Make launch/demo status one explicit product fact shared by landing, signup, upload, and policy surfaces. During a test phase, place the personal-photo restriction before upload and demonstrate with provided samples. Before opening personal uploads, replace conditional readiness prose with verified operator/provider/retention details. Do not invent security or legal claims to make the copy sound reassuring.

**Acceptance:** The answer to “May I use my family's real photos here today?” is unambiguous before account creation and before upload.

### A5 — P2: Account screens lose the app's action hierarchy

**Observed:** On Email akunmu, “Jadikan email utama,” “Kirim ulang email verifikasi,” and “Hapus email” are identical full-width coral actions, even when the sole email is already primary and verified. Status words run into the email label rather than forming scannable badges. The security overview has very large section headings and a small underlined activation link. The login form exposes two password-reset links with different voice (“Anda” versus “kamu”).

**Source:** [email.html:20](/Users/nadzeri/Documents/Upstacker/MomenRia/templates/account/email.html:20), [email actions, email.html:42](/Users/nadzeri/Documents/Upstacker/MomenRia/templates/account/email.html:42), [global auth button style, server.css:317](/Users/nadzeri/Documents/Upstacker/MomenRia/static/app/server.css:317), [login.html:9](/Users/nadzeri/Documents/Upstacker/MomenRia/templates/account/login.html:9), [login.html:13](/Users/nadzeri/Documents/Upstacker/MomenRia/templates/account/login.html:13).

**Inference:** Users must read every button to distinguish routine from destructive actions. The large marketing panel competes with account-management work and provides no route back to the current portrait.

**Recommendation:** Use a compact settings layout for authenticated account management. Show a clear current-email/status row; remove or disable actions that cannot change the current state; use secondary verification actions and a clearly separate destructive action. Apply the same primary/secondary/danger language as the app. Add “Kembali ke Foto saya” and active settings navigation. Keep the promotional story panel for entrance pages only. Standardize labels and password help without weakening validation.

**Acceptance:** One primary action is visually apparent per account task, destructive actions are distinguishable, and the user can return to their photos without using the logo or browser Back.

## Nielsen heuristic scores

| Heuristic | Score | Evidence and reasoning |
|---|---:|---|
| 1. Visibility of system status | 2 | Upload counts, saving feedback, status labels, and expiry dates are useful. Face-review feedback has no durable visible state; queued/uncertain work offers no elapsed-time context or direct next-step affordance in the notice. Source: 277, 286–290, 512–523. |
| 2. Match with the real world | 3 | Local occasion names and conversational Indonesian fit. “Referensi karakter,” “multi-sudut,” “proyek,” and formal inherited auth strings require extra interpretation. Source: 165–189, 303, 383–392. |
| 3. User control and freedom | 3 | Draft retention, undo, reusable sources, prior versions, close controls, and scoped access revocation are strong. Expired-result view has only help/delete, and returning from account pages to photos is indirect. Source: 277, 299, 368–389, 525. |
| 4. Consistency and standards | 2 | Shared app chrome and component styles are cohesive. Account action styles flatten danger/secondary meanings; template-card image/title open detail while arrow enters studio; feedback and correction feel disconnected. Source: 94, 303, account/email.html:42, CSS317. |
| 5. Error prevention | 3 | Consent, file constraints, duplicate-position validation, frozen state, retained versions, and deletion confirmation are good. Selected-face context vanishes in correction; file input remains visible for the operation that does not use it. Source: 219–258, 276, 391, 488. |
| 6. Recognition rather than recall | 2 | Numbered faces and reference thumbnails help. Users must remember which face needs work and what feedback they submitted; mobile controls and source/target comparison are separated. Source: 191–196, 277, 303, 391. |
| 7. Flexibility and efficiency | 3 | Batch upload, source reuse, undo, template switching, versions, and export formats provide meaningful shortcuts. The mobile journey is long and optional reference generation appears in the main preparation path. Source: 206–264, 363–389. |
| 8. Aesthetic and minimalist design | 2 | Landing composition is strong and product-specific. Repeated template context, oversized working-page spacing, parallel result actions, and overemphasized settings actions reduce task hierarchy. Live desktop/mobile evidence plus CSS200, 236, 317, 440. |
| 9. Error recognition and recovery | 2 | Connection text is actionable; forms retain useful context; batch partial failure is carefully explained. Some failure/uncertain messages tell people to contact help without an immediate action, and account recovery routes assume login. Source: 61–63, 255–258, 289, 316. |
| 10. Help and documentation | 2 | FAQ, guide, privacy, and contextual project support are present. The photo-quality guide is text-only; expired-source recovery is vague; locked-out account help is inaccessible. Source: 100, 302, 306, 316. |
| **Total** | **24/40** | **Acceptable: substantial flow and hierarchy improvements required.** |

## Cognitive load

The landing page is relatively focused. The studio and result page fail six of the skill's eight checklist items in at least one major state: single focus, chunking, immediate hierarchy, one decision at a time, minimal simultaneous choices, and working-memory support. Related items are visually grouped, and dialogs provide some progressive disclosure, so those two checks pass partially. This is a high-load working flow under the skill's checklist, not a scientific estimate of individual users' memory capacity.

Concrete decision points above four visible options:

- Catalog collection view exposes six collection links, three filters, and a grid of nine templates. Those are not nine equally urgent actions, but on desktop the user still has to choose which level of navigation to use. Keep count + occasion selection as the primary entry; treat refinements as refinements.
- Result sidebar simultaneously offers all-face acceptance, two to four face corrections, greeting, download, export format, new generation, help, and deletion. Visually grouping them helps but does not give a clear sequence.
- Four-person preparation adds four source slots, optional per-face reference controls, template switching, undo, generation, and project navigation. Put optional references behind an explicitly optional quality tool, with a short explanation of when they help.
- Account email management offers four submit actions around an already verified address. State-aware actions can eliminate decisions rather than merely style them.

The strongest memory bridge is selected face → comparison feedback → closed dialog → correction selection → generic correction modal. Keep the face identity and review status continuous across that sequence.

## Emotional journey

1. **Arrival:** Warm, hopeful, socially specific. The copy recognizes distance and occasions without technical framing. Keep this.
2. **Selection:** Attractive pictures create anticipation, but only finished catalog examples are shown. There is no source-photo → final-composition demonstration to establish what changes and what remains recognizable. Use a truthful worked example with permission, not fabricated quality proof.
3. **First upload:** An unexpected login jump is a valley. The selected template is preserved successfully, but the entry screen does not explain “Masuk untuk melanjutkan Lebaran Bersama” or show the chosen template. Add that context before the transition.
4. **Preparation:** Users are reassured about source retention and ownership, then confront extra “referensi karakter / multi-sudut” vocabulary. Keep optional quality tools out of the basic happy path unless evidence shows they improve outcomes.
5. **Waiting:** “You may leave and return” is excellent reassurance. Add elapsed state and a direct help route where waiting becomes uncertain. Do not promise completion times without measurement.
6. **First result, the expected peak:** The portrait should dominate, followed by a coherent face check. Instead, feedback and correction scatter across separate controls. Make “Cek 2 wajah” a short guided review whose state remains visible.
7. **Saving, the expected ending:** Mobile saving is far down the page; greeting and format choices are separate detours. A final save panel should clearly name the selected version, free watermark quality, expiry, and destination format. Acknowledge the saved/downloaded action without implying a browser download succeeded if it has not been verified.

## Per-page and state recommendations

| Page / state | Specific change |
|---|---|
| Home | Preserve visual world. Add one truthful source-to-result example. Surface “1–4 orang,” watermark, and email requirement near the entry action with minimal copy. Make demo/readiness state explicit if applicable. |
| Catalog root | Reduce working-page top spacing. Let users reach a first collection choice in the initial mobile screen. Prefer occasion and people count as the first two decisions; show search as a useful alternative. |
| Collection | Use a compact category selector on mobile and a scannable thumbnail grid. Distinguish “Lihat detail” from “Pakai template” if both routes remain; avoid an unlabeled arrow suggesting the same destination as the card. |
| Template detail | Keep generous image and preparation list. Place email requirement and free-output quality before the primary action. For graduation examples, retain the campus/AI disclaimer. |
| Empty studio | Bring upload progress and upload action next to the photo. Collapse repeated template information. Explain the login requirement before a photo-target click redirects. |
| Filled studio | Show sources adjacent to their target positions. Keep batch/reuse/undo. Place “Buat foto” in a visible contextual action area. Hide optional reference complexity behind a clearly described action. |
| Single upload | Include selected face number and miniature template context in the dialog. A local chosen-file preview would help users catch the wrong photo before upload. Keep file type, maximum size, and retention adjacent. |
| Batch upload | Keep the review-before-send behavior. Use a compact target overview that remains understandable when scrolling between mappings; ensure the final action is reachable without scrolling a long nested dialog. |
| Template change | Retain explicit warning that placements will clear. Preview the new slot count and keep a one-tap route to reassign saved sources. |
| Character references | Rename around the user's outcome, such as “Bantu jaga kemiripan,” and explain when an optional additional reference is useful. The current “Referensi karakter” label sounds like production internals. |
| Draft / queued | Say what is saved, the current stage, and whether any action is needed. Provide direct return/help actions in the same status block. |
| Failed / uncertain | Keep previous results available. Put “Buka draf” and “Minta bantuan” beside the relevant explanation; make restart eligibility clear. Real provider failures need separate validation. |
| Result | Make face review a persistent checklist and combine correction with the affected face. Keep selected version obvious. Separate review, optional personalization, and saving. |
| Face comparison | Keep original vs output labels. After an issue is recorded, explain whether repair has started and offer correction. Retain selected face in the next screen. |
| Correction | Show target face thumbnail/number. Hide replacement input until needed. Keep the same-person consent relevant to the selected operation. |
| Versions | Name corrections as well as greetings in the main version list, as the comparison dropdown already does. Provide useful face-scale mobile comparison; the whole-portrait thumbnails are too small for fine assessment. |
| Greeting | Add an on-photo preview or clear placement sample before creating a new version. Keep the guarantee that faces are unchanged and the ability to remove text. |
| Export | Combine “Download preview” and format selection into a simple save flow. Explain practical uses in plain Indonesian. Preserve non-cropping behavior, while previewing how much framing a portrait/Story format introduces. |
| Expired result | Provide a direct “Buat foto baru” or supported recovery route. “Help or delete” is an emotionally poor ending to a family-photo experience. |
| Foto saya | Retain the inviting empty state. For populated libraries, add a clear new-photo action, visible draft/processing/ready grouping when needed, and imminent-expiry emphasis. Avoid adding filters before library size justifies them. |
| Guide | Replace part of the text-only advice with safe visual examples of acceptable, blurry, distant, and obscured faces. Separate photo-quality advice from process warnings such as not restarting a job. |
| Support | Preserve project preselection and optional 24-hour access. Add an unauthenticated account-help path. Put messages/replies where returning users can find them without traversing the FAQ and form; show a reliable response expectation if known. |
| Privacy / terms | Preserve plain-language sections. Lead with a compact summary of source/result retention and who can view photos, then full text. Resolve public/demo readiness contradictions and publish only verified claims. |
| Login / signup | Preserve brand but include chosen-template context when entering from studio. Remove duplicated reset links, harmonize inherited language, and keep verification requirement before signup. |
| Verification / reset sent | Clear destination, resend/correct-email route where supported, meaningful wait/cooldown feedback, and a public help route. |
| Email settings | State-aware actions, real status badges, secondary resend, separate destructive treatment, compact layout. |
| Password / security | Compact settings typography, plain explanation of why two-factor authentication helps and what setup requires. Keep credential changes and MFA activation for the user; they were not submitted. |
| Logout | Include a visible “Kembali ke foto saya” cancel choice alongside reassurance that drafts remain saved. |
| Disabled orders | Keep payment absent while disabled. Do not present purchase improvements as launch requirements. If enabled later, design human-readable payment states and full retry/refund/download states before release. |
| Missing/empty states | Preserve existing reset-filter and template-fallback actions. Match the recovery action to the failed task rather than sending every error back to the catalog. |

## Persona red flags

- **Jordan, confused first-timer:** Taps a face expecting photo selection and reaches login; does not know why optional character references exist; may treat “Belum mirip” as a repair command. Show context at each transition and label outcome versus feedback.
- **Casey, distracted mobile user:** Finds the preview quickly but must scroll past repeated context to act; loses track of which faces were reviewed; sees tiny whole-image comparisons. A persistent next action and per-face review state address the actual interruption problem.
- **Sam, accessibility-dependent user:** Basic headings, labels, dialog close controls, and skip navigation exist. The important review-state distinction is absent for everyone, so a screen reader cannot announce it either. Correction controls named only “Wajah 1” need task context; future persisted review changes should be announced. This assessment did not run a screen-reader or full keyboard audit and does not assert WCAG conformance.

## Minor observations and questions for synthesis

- The typography has character; the problem is how often very large headings are used on working pages. Reduce scale selectively, not globally.
- Decorative rotation fits physical prints on the landing page. Keep working previews upright and predictable.
- Native file inputs display browser-localized English in the observed browser. A branded accessible picker label can clarify the action, but do not replace a robust native control merely for style.
- A stale “Berhasil masuk sebagai outsider@example.com” flash appeared on the first login render in the disposable environment. Shared test sessions may have caused it, so it is not classified as a reproducible product defect here.
- Repeated “ya / yuk / kok / nggak” makes the voice friendly, but can be reduced in dense operating instructions to improve scanning. Keep the tone; tighten the wording.
- Version, format, correction, and reference tools should answer “What does this help me do?” before exposing implementation terms or pixel dimensions.

Questions for the parent to include if further direction is needed: (1) Should the first revamp target the mobile studio/result journey or the account-access and trust gaps? (2) Should the warm scrapbook identity be retained with a quieter workspace, or should an entirely new visual world be explored? (3) Is the next release a clearly labeled synthetic demo or a service accepting real family photos? The third answer changes essential product copy and upload gates, not just aesthetics.

Skipped in Assessment A: production AI quality/latency, real payment behavior, sending support messages, credential/MFA changes, irreversible deletion, complete screen-reader/keyboard testing, and all 28 individual template variants. These limits must remain explicit in the combined audit; synthetic success is not evidence of production readiness.
