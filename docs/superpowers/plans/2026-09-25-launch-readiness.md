# MomenRia Launch Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Prepare the complete non-payment customer experience and repeatable launch checks.

**Architecture:** Keep Django APIs and server-owned state. Extend the existing plain JavaScript app and CSS, reuse current portrait assets, and run Playwright against an isolated local Django database with a synthetic worker.

**Tech Stack:** Django 5.2, Python 3.13, PostgreSQL/SQLite, vanilla JavaScript/CSS, Playwright Test.

**Spec:** `docs/launch-spec.md`, scoped from `MomenRia_Product_Requirements_v1.docx`.

## Global Constraints

- `PAYMENT_PROVIDER=disabled` for this release.
- `PUBLIC_ACCESS=false` for real customer data; production must reject shared-owner access.
- Sources default to 7 days; results default to 30 days. Display actual configured values and exact result expiry.
- Preserve one creation per verified account and one shared correction per project. Server remains authoritative.
- No new UI framework or build pipeline. Add Playwright as a development dependency only.
- No repository metadata exists in this workspace; leave reviewable files without creating commits or deploying the running Docker stack.

## Review Focus

1. A paused template must not break existing projects or results: include frozen template data in project responses and test viewing an existing project after pause.
2. Slow responses and job polling must not erase form input, reopen stale routes, or create duplicate operations: test delayed support responses and double submissions.
3. Expired references/results must not appear usable: test expiry UI and owner-only download denial.
4. Shared-owner demo mode must never accept production family photos: test production configuration rejection and explicit demo disclosure.
5. Phone widths, keyboard-only use and long content must retain reachable actions: browser tests on desktop Chromium and mobile WebKit, plus screenshots.

## Task 1: Browser harness and baseline

**Files:** `package.json`, `playwright.config.js`, `tests/e2e/server.py`, `tests/e2e/launch.spec.js`, `.gitignore`.

**Interfaces:** Harness starts loopback port 8765 with a temporary database/media root, seeded catalog and test accounts; it exposes only existing app routes.

- [x] Install pinned Playwright development dependency and browsers.
- [x] Add isolated test server using Django settings overrides, migrations, test catalog and synthetic worker. Never source `.env`.
- [x] Start with failing public experience assertions:
  ```js
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Jarak boleh jauh. Foto keluarga tetap utuh.' })).toBeVisible();
  await page.getByRole('link', { name: 'Jelajahi template', exact: true }).first().click();
  await expect(page.getByLabel('Cari template')).toBeVisible();
  ```
- [x] Run `.venv/bin/python manage.py test --noinput` and `node --test test-*.cjs`; record existing failures separately.

## Task 2: Landing, catalog and information pages

**Files:** `templates/app.html`, `static/app/server.js`, `static/app/server.css`.

**Interfaces:** Use `GET /api/v1/templates` (`items`, `offers`, `admission_enabled`) and session policy. Routes: `/`, `/templates`, `/template/:id`, `/studio/:templateId/:projectId?`, `/guide`, `/support`, `/privacy`, `/terms` inside the existing hash router.

- [x] Build responsive landing page with actual portrait art, three steps, privacy/retention explanation and honest AI disclosure.
- [x] Build searchable/filterable catalog, no-match recovery and template detail; preserve selection in direct studio URLs.
- [x] Fill guide, FAQ, privacy and terms with supported behavior; show configured retention, no fabricated quality or response-time promises.
- [x] Verify each route and missing-route recovery:
  ```js
  await page.goto('/#/templates');
  await page.getByLabel('Jumlah orang').selectOption('2');
  await expect(page.locator('.template-card')).toHaveCount(1);
  await page.getByLabel('Cari template').fill('tidak-ada');
  await expect(page.getByText('Belum ada template yang cocok.')).toBeVisible();
  ```

## Task 3: Launch capabilities and account safety

**Files:** `accounts/api.py`, `accounts/tests.py`, `momenria/settings.py`, `.env.example`, `catalog/api.py`, `templates/allauth/layouts/base.html`, `templates/account/login.html`, `templates/account/signup.html`, `templates/account/password_reset.html`.

**Interfaces:** Add session capabilities (`payments_enabled`, `corrections_enabled`) and allowance state; preserve existing response fields. Admission status reflects configured AI availability.

- [x] Add capability fields; hide payment navigation/actions when disabled.
- [x] Default environment example to private accounts and reject production shared-owner mode.
- [x] Brand account layouts while retaining Django forms, CSRF, verification, reset and MFA behavior.
- [x] Test real login, signup validation, logout and reset pages; assert disabled payment capability and production guard.
  ```python
  self.assertFalse(self.client.get('/api/v1/session').json()['capabilities']['payments_enabled'])
  ```

## Task 4: Complete studio and result lifecycle

**Files:** `projects/api.py`, `projects/result_services.py`, `projects/tests.py`, `static/app/server.js`, `static/app/server.css`, `tests/e2e/launch.spec.js`.

**Interfaces:** Embed project template metadata for unpublished versions; preserve source/job/result schema. `GET /api/v1/results/:id/preview?download=1` returns an owner-only attachment. Existing master endpoint still requires entitlement.

- [x] Correct draft matching and resume links, show thumbnails and expired sources, disable frozen/processing inputs and show admission/allowance reasons.
- [x] Guard submissions while pending; retain upload dialog on failure with an inline error; handle stale revisions by reloading authoritative state.
- [x] Render understandable queue/failure states, selected result version, free download, zoom, feedback, greeting and correction allowance. Poll without resetting unrelated form input.
- [x] Render greetings from their generation root so editing/removing text cannot stack old captions.
- [x] Exercise upload → reload → generation → result → download → greeting → version switch → support → deletion. Verify a second browser cannot read another owner's media.
  ```js
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Unduh pratinjau' }).click();
  expect((await download).suggestedFilename()).toMatch(/^momenria-preview-/);
  ```

## Task 5: Browser evidence and release handoff

**Files:** `README.md`, `docs/launch-readiness.md`, `docs/operations.md`, `docs/implementation-status.md`, `tests/e2e/launch.spec.js`.

- [x] Run browser checks on desktop Chromium and mobile WebKit; inspect full-page landing/catalog/studio screenshots and fix discovered problems.
- [x] Run complete backend and existing Node suites, migration check and Django deployment checks with documented environment limitations.
- [x] Review changed code against five review-focus cases; fix blocking findings and rerun affected checks.
- [x] Record exact test commands/results, remaining owner/provider tasks and go/no-go gates. Link plan and browser report from README.

## Production launch sequence (payments excluded)

| Gate | Owner | Evidence required before public uploads |
|---|---|---|
| Provider eligibility | Product owner + processor | Approved privacy/child-image terms, retention/deletion contract, cost ceiling, generation and targeted correction routes |
| Catalog quality | Product owner | Consented 2/3/4-person held-out likeness and unchanged-face correction results per immutable variant; publish only passing counts |
| Infrastructure | Operator | HTTPS domain, separate production secrets and PostgreSQL roles, private media, worker and maintenance, writable greeting result volume |
| Identity | Operator | `PUBLIC_ACCESS=false`, delivered verification/reset emails, tested owner isolation and staff MFA |
| Reliability | Operator | Off-host encrypted backup and timed restore/tombstone drill, outage/uncertain-job drills, deletion and budget alerts |
| Service policy | Product owner | Approved privacy/terms, processor disclosures, support contact/hours, guardian policy and incident owner |
| Device validation | Product owner | Physical iPhone Safari and Android Chrome, slow/interrupted upload, sleep/resume, enlarged text and screen reader |
| Admission | Operator | Positive bounded daily budget, passing templates and provider, capacity measurements; then limited non-payment pilot |

Payment checkout, merchant contract, callbacks, refunds and paid conversion remain deferred. Do not claim production launch readiness until the non-payment gates above have real evidence.

## Execution record

Tasks 1–5 completed locally. See `docs/launch-readiness.md` for test evidence, independent-review fixes and execution decisions. Production gate table remains open; checked implementation steps do not mean public release approval. No Git repository exists here, so Git worktree/commit helper steps were inapplicable. Test infrastructure was isolated instead.
