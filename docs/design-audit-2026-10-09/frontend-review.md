# Frontend implementation review

9 October 2026. Read-only source review against the approved README and implementation plan; no score assigned. Source was changing during review, so locations identify the reviewed snapshot.

## Scoped re-review disposition

All six frontend findings below are resolved in the latest source. This disposition checks implementation, not an independently executed browser suite.

| Finding | Disposition and evidence |
|---|---|
| Explicit studio silently creates a replacement | Resolved. `studio()` shows loading/error recovery while an explicit project is unavailable; no upload or create controls appear. `revamp.spec.js` covers an explicit missing studio. |
| Stale requested projects and older active jobs | Resolved. `refreshProjects()` fetches the requested project and cached active projects outside the first page, removes direct 404s, preserves non-404 errors visibly, and merges successful detail responses. Focused browser coverage for the older-active branch was requested; test execution belongs to root verification. |
| Main controls lose focus | Resolved. Focus identity includes form ID plus field name and anchor href. Main-form draft values survive same-route startup renders; pending main submissions are not replaced. The delayed-catalog test now asserts retained message value and focus. |
| Safe-area taskbar overlap | Resolved in CSS. Final creation/save action offsets and document spacers include `env(safe-area-inset-bottom)`. Physical-device measurement remains outside this review. |
| Wrong error input | Resolved. `showError()` reads `payload.field`, matching the API's flattened error contract. |
| Split saving workflow | Resolved. The primary result action is now “Simpan foto”, opening one native dialog with original, square, portrait and Story choices. Download occurs inside that sheet; the fixed mobile action uses `.save-photo`. Relevant browser test callers were updated. |

## Account-context follow-up — resolved

**P2 — Password recovery still loses the selected destination** (`templates/account/password_reset_help_text.html:1`, `templates/account/password_reset.html:7`, `templates/account/password_reset_from_key_done.html:15`). Enter login from a selected studio and choose “Lupa kata sandi?”. The reset link has no return target; the reset form and return-to-login links also omit it. The otherwise safe account-context fix covers login, signup, verification and MFA, but this recovery branch does not yet meet F01's requirement to retain the selected template/destination throughout authentication. Preserve a validated same-browser return context across reset and the subsequent login; do not broaden redirect trust or include private project metadata.

## Corrections reviewed during this pass

- Stable header signature now avoids rebuilding navigation during unchanged-route status updates.
- Same-route startup rendering preserves main-form values and avoids replacing an actively submitted main form.
- Negative face feedback now uses the same correction availability checks as the ordinary correction actions.
- Version comparison now holds a selected face across both versions and starts mobile comparison on a face crop.
- The first home CTA now discloses watermark and 768px output; catalog cards now have a visible “Pakai template” action.
- Catalog return links preserve the originating catalog route.
- Backend trusted-proxy rate limiting passed source re-review; account return context now identifies the selected published template and rejects unsafe destinations.

Not checked: Database suites, live Docker/PostgreSQL behavior, physical-device safe areas, screen-reader tasks, or completed browser interaction. The local public page was observed; the browser connection failed during disposable synthetic sign-in. No personal account or image data was used.

Final recovery re-review approved the same-browser validated return context through reset receipt, emailed token, completion and subsequent login;22 account tests pass. Later visual/source review found SVG hidden-attribute and asynchronous ticket-reply draft gaps; both were reproduced in focused browser regressions and corrected. Final source review also approves direct assigned-photo position markers and consistent authored SVG icons.
