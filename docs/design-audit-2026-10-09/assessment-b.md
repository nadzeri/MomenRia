# Assessment B — Technical and browser evidence

Independent technical assessment for `templates/app.html`, `static/app/server.js`, `static/app/server.css`, and account templates, dated 2026-10-09. This assessment did not read Assessment A or any other assessment output. The parent owns the combined report, route inventory, account/admin coverage, and server cleanup.

## Implementation integrity verdict

**Qualified pass.** The implementation has a coherent product-specific workflow: template collections, numbered face placement, privacy consent, saved drafts, per-face correction, version comparison, retention dates, and explicit synthetic-result labeling. Shared render helpers, native forms/dialogs, and consistent route navigation provide a strong base. Verified small-text and color-state problems weaken readability; asynchronous status/focus handling needs targeted hardening. Detector palette preferences are not evidence that the product needs a visual redesign.

## Audit health score

| Dimension | Score | Main evidence |
|---|---:|---|
| Accessibility | 2/4 | Two verified text-contrast failures; good labels, keyboard focus and native dialog behavior; background status/focus risk remains |
| Performance | 3/4 | Small plain-JS app, WebP/lazy images, local font; sequential authenticated initialization and no measured production vitals |
| Responsive design | 3/4 | No horizontal document overflow in measured 390/320px paths; adequate main touch targets; 9.6px mobile navigation labels |
| Theming | 2/4 | Base palette tokens exist; many repeated component colors remain literal and caused a hover-state mismatch |
| Implementation integrity | 3/4 | Coherent system with isolated semantic and state problems; detector style warnings manually qualified |
| **Total** | **13/20** | **Acceptable — significant targeted improvements remain** |

No P0 blocker was reproduced. Seven recommendations: **2 P1, 3 P2, 2 P3**. This is a bounded technical audit, not a WCAG conformance certification or production performance test.

## Priority findings

### B1 — P1: Closing CTA loses text contrast on hover

- **Location:** `static/app/server.css:28` and `static/app/server.css:120`; CTA markup `static/app/server.js:132`.
- **Category:** Accessibility / Theming.
- **Verified evidence:** `.closing-card .btn` gives the closing CTA cream text `#f5f3ec` on ink. The more-specific `.btn.primary:hover` replaces only its background with `#ff936f`. Calculated contrast becomes **1.959:1**, below **4.5:1** for its normal-size text. The rendered-home detector independently reports this same 2.0:1 hover combination.
- **Impact:** The principal closing action becomes harder to read exactly when desktop users target it.
- **Recommendation:** Give the closing CTA an explicit hover color pair, or express filled button variants through paired foreground/background tokens so shared hover rules cannot combine unrelated colors.
- **Standard:** WCAG 2.2 SC 1.4.3; hover text is covered. [W3C contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
- **Suggested command:** `$impeccable harden`, then `$impeccable polish`.
- **Evidence level:** Detector + source cascade + contrast computation; native hover screenshot unavailable because the supported interaction API exposes no hover action.

### B2 — P1: Form placeholder text is below AA contrast

- **Location:** `static/app/server.css:179` with input backgrounds at `static/app/server.css:177`; catalog field at `static/app/server.js:151`, support fields at `static/app/server.js:316`.
- **Category:** Accessibility.
- **Verified evidence:** Live browser computed placeholder `rgb(128,136,121)` (`#808879`) on white; calculated contrast **3.674:1**. The inputs use 16px normal text, requiring 4.5:1. This is additional manual evidence, not a detector finding.
- **Impact:** Search hints and support examples are harder to read for low-vision users. Visible labels are present, so this is not an unlabeled-input issue.
- **Recommendation:** Use the existing muted token (`#66645f`) or another tested placeholder foreground with at least 4.5:1 on white.
- **Standard:** WCAG 2.2 SC 1.4.3 explicitly includes placeholder text. [W3C contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
- **Suggested command:** `$impeccable harden`.

### B3 — P2: Important mobile labels and AI disclosure are too small

- **Location:** `static/app/server.css:461` (mobile navigation `0.6rem`), `static/app/server.css:394` (hero AI disclosure `0.57rem`), `static/app/server.css:41` (eyebrows `0.68rem`), `static/app/server.css:94` (template occasion labels `0.62rem`). Disclosure markup: `static/app/server.js:121`.
- **Category:** Responsive design / Accessibility.
- **Verified evidence:** Mobile navigation is **9.6px**; hero AI disclosure resolves to **9.12px** because `.hero-visual .sample-note` overrides the later, less-specific `0.59rem` rule. Live catalog eyebrow measured **10.88px**. The detector finds 40 repeated undersized UI instances across five rendered views; these are repeated occurrences, not 40 separate defects.
- **Impact:** The five persistent navigation labels, AI-result caveat, and secondary metadata require extra visual effort on phones. Small text is particularly unfortunate for the product's important “example AI / results may vary” disclosure.
- **Recommendation:** Set a practical 12–14px baseline for persistent functional labels and material disclosure; simplify redundant eyebrow copy where extra space is needed. Preserve the current generous touch boxes.
- **Standard:** Quality/usability issue, **not an automatic WCAG AA failure based on font size alone**.
- **Suggested command:** `$impeccable typeset`, `$impeccable adapt`.

### B4 — P2: Background project updates replace the focused UI and have no dedicated status announcement

- **Location:** `static/app/server.js:44` (plain notice), `static/app/server.js:286` (job notice), `static/app/server.js:331` (whole main replacement), `static/app/server.js:560` (poll rerender with `focus:false`).
- **Category:** Accessibility / Implementation integrity.
- **Source-verified risk:** When project JSON changes, polling replaces all of `#main`; `focus:false` suppresses deliberate focus restoration but does not preserve a focused descendant that was removed. Job status appears inside a plain `<div class="notice">`, with no status/live-region semantics. The toast announces initial submission, but polling itself does not announce queued → processing → ready/failure transitions.
- **Impact:** A keyboard or screen-reader user inspecting a result while a job finishes can lose their place and may not receive the new status without exploring the page again.
- **Recommendation:** Keep a persistent status node with polite announcements and update the changed region; if a whole render is retained, restore the meaningful active control when it still exists. Do not move focus on every poll.
- **Standard:** Potential SC 4.1.3 concern; definitive assistive-technology behavior **was not tested with a real screen reader**. [W3C status guidance](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html).
- **Suggested command:** `$impeccable harden`.

### B5 — P2: All authenticated routes wait for project loading before first render

- **Location:** `static/app/server.js:566` and `static/app/server.js:338`.
- **Category:** Performance / Error recovery.
- **Source-verified evidence:** Initialization awaits `/session`, then `/templates`, then `refreshProjects()`, which itself awaits `/projects` and another `/session`, before rendering. An authenticated landing/help/catalog view therefore sits behind four sequential API reads; a project-read failure routes the entire app into the initialization failure screen.
- **Impact:** A slow or unavailable project list unnecessarily delays access to templates and help. This will grow more noticeable with longer-lived accounts and slower mobile networks.
- **Recommendation:** Render the shell and requested public content once their dependencies are ready; load private project data only where needed or in parallel when safe, with a local retry/error state. Preserve the existing retry affordance.
- **Evidence limit:** This is a verified dependency-chain risk, **not a measured latency regression**. No production throttling/LCP/INP measurements were taken.
- **Suggested command:** `$impeccable optimize`, `$impeccable harden`.

### B6 — P3: Guide headings skip a level

- **Location:** `static/app/server.js:96` and `static/app/server.js:305`.
- **Category:** Accessibility / Implementation integrity.
- **Verified evidence:** The guide accessibility tree goes from its H1 directly to three H3 step headings, then H2 sections. This is also a `skipped-heading` detector finding. The same `steps()` component is appropriate under the homepage's H2, explaining how the guide inherited the mismatch.
- **Impact:** Heading navigation conveys an inaccurate hierarchy on the guide.
- **Recommendation:** Make the guide's steps H2, or introduce a meaningful H2 section around them. Avoid adding a heading solely for detector compliance.
- **Standard:** Semantic quality issue; a skipped level alone is not being declared a WCAG failure here.
- **Suggested command:** `$impeccable harden`.

### B7 — P3: The palette system stops before component states

- **Location:** `static/app/server.css:2`, `:28`, `:121`, `:125`, `:158`, `:177`, `:201`, `:210`, `:248`, `:260`, `:310`.
- **Category:** Theming.
- **Source evidence:** Core color variables coexist with repeated literals such as `#fffefa`, `#ffc1ac`, `#c5c2bb`, and independently chosen hover colors. B1 is a concrete example of foreground/background state drift.
- **Impact:** Repeated edits are required to maintain consistent states and contrast. No dark-mode UI is promised, so absence of dark mode is not counted as a user-facing defect.
- **Recommendation:** Tokenize only repeated semantic surfaces, field borders, and button state pairs already used. Do not introduce a new theme switch or broad token framework.
- **Suggested command:** `$impeccable document`, then `$impeccable polish`.

## Detector results and false-positive review

Actual launcher: `/Users/nadzeri/.codex/plugins/cache/openai-curated-remote/impeccable/4.3.1/skills/impeccable/scripts/impeccable`.

- Source scan: `detect --json templates static/app/server.js`, exit 0, **0 findings**. Separate source scans also returned empty arrays. Django `{% static %}` stylesheet URLs cannot be resolved by the detector, and the app renders from JS template strings, so those zeroes are **not a clean bill of health**.
- To improve coverage, the native browser's read-only DOM export captured five real rendered views. Only the stylesheet link was adjusted in evidence copies from `/static/app/server.css?...` to `../../../static/app/server.css?...`, allowing the CLI to resolve the real deployed stylesheet. The application source was unchanged.
- Rendered-home scan: exit 2, **31 findings**. Other four views: exit 2, **44 findings**. Combined **75 occurrences** across **9 rule IDs**. All final rendered scans resolved CSS without stderr warnings.
- Full outputs: `evidence/b-detector-rendered-home.json`, `evidence/b-detector-rendered-routes.json`. Consolidated rules/snippets/files: `evidence/b-detector-summary.json`.
- File counts: home 31; catalog 14; studio 12; guide 10; privacy 8. The generated DOM is serialized, so detector line numbers are 0; verified production source lines are supplied above.

| Rule | Occurrences | Verification / interpretation |
|---|---:|---|
| `undersized-ui-text` | 40 | Verified; combine recurring mobile labels/disclosures under B3, do not count every occurrence as a separate issue |
| `tiny-text` | 7 | Sizes exist; overlaps with B3; some short decorative kicker text is lower priority |
| `gray-on-color` | 9 | **Rejected as an accessibility failure**: `#4c4843` on lime/lilac/peach calculates 7.362:1 / 5.184:1 / 5.820:1, all AA for body text |
| `kicker-above-heading` | 9 | Pattern exists; design preference / redundancy observation, not technical failure by itself |
| `cream-palette` | 5 | **Not a defect on its own**: established warm palette is coherent with photo-memory content |
| `low-contrast` | 2 | Closing CTA hover is valid B1. Guide's × glyph is a symbol with adjacent redundant heading, 3.5:1; the detector treated it as ordinary text. Do not count it as a 4.5:1 body-text failure |
| `ai-color-palette` | 1 | **Rejected as a technical defect**: lilac-section heading color `#4e356f` is intentional, with 5.819:1 contrast on `#cbbcf1`; no purple gradient or cyan-on-dark UI |
| `extreme-negative-tracking` | 1 | Actual H1 `-0.05em`; no clipping/collision seen in the mobile screenshot, so no technical failure asserted |
| `skipped-heading` | 1 | Verified B6 |

An initial evidence-copy attempt used an absolute filesystem stylesheet path that the detector treated as root-relative; it warned about missing CSS and reported a spurious flat hierarchy. That was corrected to a relative path and the final saved scan replaced it. The source/browser hierarchy clearly has H1 42.4px, collection H2 25.6px and 16px inputs at 390px. The failed intermediate scan is not included in the 75 final findings.

## Browser observations and positive findings

Browser work used a fresh native CUA IAB tab, first at `127.0.0.1:8766`, then the parent's isolated `localhost:8768` host for a disposable authenticated mobile account. No production access, payments, actual image uploads, generations, deletion, or support message transmission were performed by this assessment.

- **390×844:** visually checked home, login, catalog, empty search, collection, studio, upload dialog and support validation. Document scroll width was 375px within the scrollbar-adjusted 375px client width on measured home/catalog/studio/support views.
- **320×800:** measured support, catalog and studio at 305px client/scroll width; no horizontal document overflow. Also inspected empty projects, guide and privacy through the native accessibility tree.
- **Touch targets:** mobile navigation measured **67×56px** at 390px. Face markers **44×44px**; dialog close **44×44px**. Login text link was approximately **36.8×44px**, above WCAG 2.2's 24px minimum on both axes. No AA violation is claimed merely for falling short of the preferred 44px width. Checkbox input was 20px, but it has a large enclosing clickable label, so it is not treated as a 20px-only touch target. [W3C target-size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).
- **Keyboard/dialog:** dialog opened with focus on labeled close button; Tab reached the labeled file input with a visible **3px ink outline / 5px offset**. Empty submit focused the required file input and showed the browser's validation message. Escape closed the dialog and returned focus to the invoking face marker.
- **Labels/state:** actual input labels, native selects, named face controls, native dialog, `aria-current` navigation, `aria-pressed` versions, and `role="alert"` form errors are good foundations. Skip link and deliberate main focus support route changes.
- **Error recovery:** search retained focus while changing results, showed a clear zero-results message, and reset to 6 collections / 28 templates. Support permission without a project produced a specific inline alert and preserved entered subject/message. The guard fired before an API call, so no ticket was sent.
- **Performance fundamentals:** JS is 88,643 bytes, CSS 43,923 bytes, self-hosted WOFF2 76,868 bytes. Hero WebPs are 53,988 and 89,186 bytes. Other cards use lazy loading, explicit image dimensions, and WebP assets. There is no runtime frontend framework dependency in `package.json`.
- **Reduced motion:** existing rule disables animation/transitions while retaining visible textual loading status and static layout. No evidence of lost essential state was found; do not flag the global reduction solely because it is global.
- **Console:** final captured warning/error log list was empty (`evidence/b-console.json`).

Screenshots: `b-mobile-home.png`, `b-mobile-catalog.png`, `b-mobile-empty-search.png`, `b-mobile-studio.png`, `b-mobile-upload.png`, `b-mobile-support-validation.png`, `b-320-support.png`, `b-320-projects-empty.png`, `b-320-studio.png`. Machine-readable measured observations: `evidence/b-browser-measurements.json`.

## Run notes and limits

- Target: production source paths above; legacy root `index.html` / `app.js` excluded from production technical scoring.
- Ignore list: parent confirmed no `.impeccable/critique/ignore.md` exists. Impeccable context was already run once by parent; not rerun.
- Independence: only source, skill references, own browser state and own B evidence read. No A report or other assessment findings consumed.
- Browser visibility: kept in background. Responsive viewport override was reset; B-created tab closed.
- Overlay injection: **not available**. CUA explicitly exposes Playwright evaluate as read-only and provides no mutable script injection method. No title/script mutation was attempted through that restricted evaluator, no detector live server was started, and no user-visible overlay is claimed. Native screenshots, DOM measurement and CLI scans of rendered markup are the fallback.
- Server cleanup: no server started/stopped by B; parent owns both preview servers.
- Evidence cleanup: report and `b-*` evidence retained intentionally. No app source edits, dependencies, tests or commits introduced.
- Performance limits: a native DOM evaluation attempt found `performance` unavailable, so no navigation-resource timing, LCP, CLS, INP, throttling or production-cache claims are made. File-size and dependency evidence only.
- Coverage limits: no real VoiceOver/NVDA run, no 200% text-only zoom, no production AI/payment/provider calls. Parent covers remaining account/admin/transactional surfaces and route completeness.
- Suggested sequence: harden the contrast pairs and asynchronous status behavior; typeset/adapt essential small text; optimize initialization; fix guide semantics and consolidate existing tokens; finish with `$impeccable polish` and rerun audit.
