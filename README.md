# MomenRia

Single-server Django implementation of MomenRia's private family-portrait workflow. Browser state is no longer authoritative: accounts, projects, stable face assignments, jobs, costs, results, orders, entitlements, support, and deletion live on server.

The root `index.html`, `app.js`, `model.js` and `styles.css` are archived browser-only prototypes retained for regression tests. They are not the served application, launch evidence or current product policy.

## Local test setup

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD, DATABASE_URL, and DJANGO_SECRET_KEY in .env.
docker compose build
docker compose run --rm web python manage.py collectstatic --noinput
docker compose run --rm web python manage.py seed_catalog --test-publish
docker compose up -d
```

Open `http://localhost:8080`. Create superuser:

```bash
docker compose run --rm web python manage.py createsuperuser
```

Customer accounts are private by default (`PUBLIC_ACCESS=false` in `.env.example`). Production rejects `PUBLIC_ACCESS=true`. That setting remains available for isolated test demos only: all visitors share one owner's data. An existing local `.env` is not automatically changed; check it before deploying. Admin and operator access require authentication and MFA.

Compose sets `TRUSTED_PROXY_HOST=caddy` for the web service. Caddy overwrites `X-Momenria-Client-IP` with its connection's remote IP, and API network rate limits accept that header only when Django's `REMOTE_ADDR` matches an address resolved for the configured proxy host. Direct development defaults to an empty trusted host and uses `REMOTE_ADDR`; spoofed headers, malformed addresses and proxy DNS failures also fall back to `REMOTE_ADDR`. Arbitrary `X-Forwarded-For` values are never used for these API limits. Keep Caddy as the directly reached edge proxy; another CDN or proxy in front would require a separately reviewed trust configuration.

Test publishing marks supplied templates as synthetic test variants. Never use `--test-publish` in production. Production catalog publication needs benchmark evidence.

## Direct development

Python 3.13 required.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_catalog --test-publish
.venv/bin/python manage.py runserver
```

Run checks:

```bash
.venv/bin/python manage.py test
.venv/bin/python manage.py check --deploy
node --test test-*.cjs
```

For real local generation, set `AI_GATEWAY_MODE=9router`, `NINE_ROUTER_BASE_URL`, `NINE_ROUTER_API_KEY`, `NINE_ROUTER_GENERATION_MODEL`, and `NINE_ROUTER_GENERATION_PATH=/images/generations`. `AI_GATEWAY_MODE=fake` and `PAYMENT_PROVIDER=fake` work only with `APP_ENV=test`; fake AI output is marked synthetic and can only use the fake payment provider in isolated test environments; real Midtrans purchases reject synthetic processing. 9Router output between `AI_UPSCALE_MIN_LONG_EDGE` and 2048 px receives a disclosed local Lanczos finishing step; smaller output is rejected. Admissions require `ADMISSION_ENABLED=true`, each published template needs worst-case `max_cost_idr`, and either `DAILY_BUDGET_IDR` must be positive or test-only `ALLOW_UNBOUNDED_TEST_BUDGET=true` must be explicit. Production rejects unbounded mode.

## Main commands

- `python manage.py runworker`: claim durable jobs with leases and fencing.
- `python manage.py maintenance`: run five-minute expiry/deletion/payment maintenance.
- `python manage.py seed_catalog`: load supplied concepts as drafts.
- `python manage.py seed_catalog --test-publish`: publish synthetic test variants in test only.

The catalog includes 28 templates for Indonesian holidays, birthdays, eight university graduation settings, pre-wedding, babies, maternity, weddings, and anniversaries. Solo portraits and university filtering are supported. See [template inventory, asset provenance, and campus references](docs/template-catalog.md). After updating, run migrations and seed the catalog to add the new drafts; test publication remains restricted to test environments.

API contract: [`openapi.yaml`](openapi.yaml). Operations and unresolved release decisions: [`docs/operations.md`](docs/operations.md). Requirement-by-requirement evidence: [`docs/implementation-status.md`](docs/implementation-status.md).

## Pricing and Midtrans readiness

The Django app now includes a landing page, searchable template catalog, template details, studio, private photo library, result review/downloads, guide, support, privacy, terms, and branded account pages. Templates are browsed through six moment collections; each collection has its own link and relevant filters. Studio's **Ganti template** picker changes the current draft before generation starts. Confirmation clears face placements while retaining uploaded photos, which can be assigned again through **Foto tersimpan**. Each account receives three lifetime successful new pictures, then pays IDR9,900 per new picture before generation. Corrections to the same picture, greetings, repeated downloads and format exports stay free. All downloads use full-quality unwatermarked masters, with root grants enforcing ownership, expiry and refund revocation. `PAYMENT_CHECKOUT_ENABLED=false` pauses new purchases while account order history remains available; keep the payment provider configured for reconciliation when money is in flight.

Pricing plan: [`Midtrans implementation plan`](docs/superpowers/plans/2026-10-10-midtrans-website-requirements.md). Review and external activation gates: [`Midtrans checklist`](docs/midtrans-review-checklist.md). Current evidence and remaining production gates: [`docs/launch-readiness.md`](docs/launch-readiness.md). A synthetic passing test is not evidence of likeness quality or production readiness.

### Browser tests

```bash
npm ci
npx playwright install chromium webkit
npm run test:e2e
npx playwright test --config=playwright.payments.config.js
npm run test:e2e:report
```

Playwright starts separate loopback Django servers on ports 8765 and 8767 for desktop and mobile. Each uses its own temporary database, private-media directory, verified test accounts, and synthetic worker so the two suites do not consume each other's rate limits. They do not read `.env`, change your existing database, call a real AI provider, or charge money. Generation scenarios use independent accounts with quota enforcement enabled. The paid suite uses separate servers on 8775/8777 and fake payment only; keep all four ports free. Desktop Chromium and iPhone-sized WebKit both run the suite; physical-device testing remains a launch gate. Reports, traces and screenshots appear under `playwright-report/` and `test-results/`.

The complete upload/generation/correction/greeting/download/support/deletion journey uses real Django APIs. Explicitly named failure-state and latency tests intercept selected responses. Backend tests cover actual paused-template access, ownership, expiry, immutable results and PostgreSQL concurrency.

To inspect an isolated preview manually:

```bash
.venv/bin/python tests/e2e/server.py --port 8766
```

Open `http://127.0.0.1:8766`. The disposable account is `desktop@example.com`, password `Portrait-test-2026!`. These credentials exist only in the temporary test server. Stop the process to discard its database/media. Catalog originals remain unchanged; smaller WebP derivatives are used only for web display.

### Character consistency

New template versions support private original-pixel character sheets, optional approved AI multi-view references, frozen per-person prompts and per-face result review. Existing template behavior stays versioned. Setup, bounded A–E evaluation and rollout gates: [character consistency runbook](docs/character-consistency-operations.md). Real likeness improvement has not yet been measured; production candidates remain gated.

### Competitive workflow improvements

Global catalog search opens matching templates directly. Studio accepts several photos in one consented upload session, with explicit face-position review and recovery after partial failures. Results support side-by-side version comparison and square, portrait, or Story/Status exports from the clean full-resolution master that preserve every image edge with native-resolution padding. Exports do not regenerate faces, increase image detail, or extend retention. See the [competitor comparison and remaining quality benchmark](docs/competitive-review.md); overall competitive superiority has not been established.
