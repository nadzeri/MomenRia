const { test, expect } = require('@playwright/test');

test('catalog keeps search and position when returning from a template', async ({ page }) => {
  await page.goto('/#/templates');
  await page.getByLabel('Cari template').fill('wisuda ui');
  await page.getByRole('link', { name: 'Wisuda UI', exact: true }).click();
  await page.goBack();
  await expect(page.getByLabel('Cari template')).toHaveValue('wisuda ui');
  await expect(page.locator('.template-card')).toHaveCount(1);
});

test('public guidance survives an unavailable account service', async ({ page }) => {
  await page.route('**/api/v1/session', route => route.abort());
  await page.goto('/#/guide');
  await expect(page.getByRole('heading', { name: 'Biar hasilnya oke, mulai dari fotonya.' })).toBeVisible();
  await expect(page.locator('#connection-status')).toContainText('akun');
  await expect(page.locator('.steps-grid h2')).toHaveCount(3);
});

test('closing action and placeholder meet readable contrast', async ({ page }, testInfo) => {
  await page.goto('/');
  const button = page.locator('.closing-card .btn');
  await button.scrollIntoViewIfNeeded();
  if (testInfo.project.name === 'desktop') await button.hover();
  const ratio = await button.evaluate(element => {
    const style = getComputedStyle(element);
    const luminance = color => color.match(/[\d.]+/g).slice(0, 3).map(Number).map(value => value / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4).reduce((total, value, index) => total + value * [.2126, .7152, .0722][index], 0);
    const a = luminance(style.color), b = luminance(style.backgroundColor);
    return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
  });
  expect(ratio).toBeGreaterThanOrEqual(4.5);
  await page.goto('/#/templates');
  const placeholder = await page.getByLabel('Cari template').evaluate(element => {
    const style = getComputedStyle(element, '::placeholder');
    const luminance = color => color.match(/[\d.]+/g).slice(0, 3).map(Number).map(value => value / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4).reduce((total, value, index) => total + value * [.2126, .7152, .0722][index], 0);
    const a = luminance(style.color), b = luminance(getComputedStyle(element).backgroundColor);
    return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
  });
  expect(placeholder).toBeGreaterThanOrEqual(4.5);
});

test('account recovery is public and owner replies stay in their ticket', async ({ page }, testInfo) => {
  await page.goto('/#/support');
  await page.getByLabel('Email yang bisa dihubungi').fill('synthetic-access@example.com');
  await page.getByLabel('Topik', { exact: true }).fill('Verifikasi contoh');
  await page.getByLabel('Pesan', { exact: true }).fill('Permintaan sintetis untuk menguji akses akun.');
  await page.getByRole('button', { name: 'Kirim permintaan akun' }).click();
  await expect(page.locator('#account-access-form .receipt')).toBeVisible();
  await page.goto('/accounts/login/');
  await page.locator('[name="login"]').fill(`competitive-${testInfo.project.name}@example.com`);
  await page.locator('[name="password"]').fill('Portrait-test-2026!');
  await page.getByRole('button', { name: 'Masuk', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Akun saya', exact: true })).toBeVisible();
  await page.goto('/#/support');
  await page.getByLabel('Topik', { exact: true }).fill('Balasan contoh');
  await page.getByLabel('Pesan', { exact: true }).fill('Pesan awal sintetis tanpa foto pribadi.');
  await page.getByRole('button', { name: 'Kirim pesan', exact: true }).click();
  const ticket = page.locator('#support-items article').filter({ hasText: 'Balasan contoh' });
  await ticket.locator('summary').click();
  await ticket.getByLabel('Jawaban untuk Balasan contoh').fill('Jawaban sintetis untuk tiket yang sama.');
  await ticket.getByRole('button', { name: 'Kirim jawaban' }).click();
  await expect(ticket.locator('.owner-reply')).toContainText('Jawaban sintetis');
  await page.reload();
  await expect(ticket.locator('.owner-reply')).toContainText('Jawaban sintetis');
});

test('late public data never erases a help draft', async ({ page }) => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/v1/templates', async route => {
    await gate;
    await route.continue();
  });
  await page.goto('/#/support');
  await page.getByLabel('Pesan', { exact: true }).fill('Pesan sintetis tetap ada saat template datang.');
  release();
  await page.waitForResponse('**/api/v1/templates');
  await expect(page.getByLabel('Pesan', { exact: true })).toHaveValue('Pesan sintetis tetap ada saat template datang.');
  await expect(page.getByLabel('Pesan', { exact: true })).toBeFocused();
});


test('an explicit missing studio never becomes a replacement draft', async ({ page }, testInfo) => {
  await page.goto('/accounts/login/');
  await page.locator('[name="login"]').fill(`competitive-${testInfo.project.name}@example.com`);
  await page.locator('[name="password"]').fill('Portrait-test-2026!');
  await page.getByRole('button', { name: 'Masuk', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Akun saya', exact: true })).toBeVisible();
  const catalog = await (await page.request.get('/api/v1/templates')).json();
  await page.goto(`/#/studio/${catalog.items[0].id}/11111111-1111-4111-8111-111111111111`);
  await expect(page.getByRole('button', { name: 'Coba buka lagi' })).toBeVisible();
  await expect(page.locator('[data-upload-slot]')).toHaveCount(0);
  await expect(page.locator('[data-generate]')).toHaveCount(0);
});

test('older active projects refresh beyond the first page and preserve navigation focus', async ({ page }, testInfo) => {
  await page.goto('/accounts/login/');
  await page.locator('[name="login"]').fill(`competitive-${testInfo.project.name}@example.com`);
  await page.locator('[name="password"]').fill('Portrait-test-2026!');
  await page.getByRole('button', { name: 'Masuk', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Akun saya', exact: true })).toBeVisible();
  const catalog = await (await page.request.get('/api/v1/templates')).json();
  const template = catalog.items[0];
  const items = Array.from({ length: 51 }, (_, index) => ({
    id: `10000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
    template_id: template.id, template, revision: 1, assignments: {}, sources: [], results: [], jobs: [],
  }));
  const older = items[50];
  older.template = { ...template, name: 'Draf lama sintetis' };
  older.jobs = [{ id: 'test-job', operation: 'creation', state: 'queued' }];
  let deleted = false;
  await page.route('**/api/v1/projects**', async route => {
    const url = new URL(route.request().url());
    if (url.pathname === `/api/v1/projects/${older.id}`) return route.fulfill(deleted ? { status: 404, json: { message: 'Proyek tidak ditemukan.' } } : { json: older });
    if (url.pathname !== '/api/v1/projects') return route.continue();
    return route.fulfill({ json: url.searchParams.has('offset') ? { items: [older], next_offset: null } : { items: items.slice(0, 50), next_offset: 50 } });
  });
  await page.goto('/#/projects');
  await page.reload();
  await page.getByRole('button', { name: 'Lihat proyek sebelumnya' }).click();
  const card = page.locator('.template-card').filter({ hasText: 'Draf lama sintetis' });
  await expect(card.getByRole('link', { name: 'Cek proses' })).toBeVisible();
  const help = page.getByRole('navigation', { name: 'Navigasi utama' }).getByRole('link', { name: 'Bantuan' });
  await help.focus();
  older.jobs[0].state = 'failed';
  await expect(card.getByRole('link', { name: 'Lanjutkan draf' })).toBeVisible({ timeout: 15000 });
  await expect(help).toBeFocused();
  await card.getByRole('link', { name: 'Lanjutkan draf' }).click();
  deleted = true;
  await page.reload();
  await expect(page.getByRole('button', { name: 'Coba buka lagi' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Lanjutkan draf', exact: true })).toHaveCount(0);
});


test('late catalog data preserves an authenticated ticket reply draft', async ({ page }, testInfo) => {
  await page.goto('/accounts/login/');
  await page.locator('[name="login"]').fill(`competitive-${testInfo.project.name}@example.com`);
  await page.locator('[name="password"]').fill('Portrait-test-2026!');
  await page.getByRole('button', { name: 'Masuk', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Akun saya', exact: true })).toBeVisible();
  await page.goto('/#/support');
  await page.getByLabel('Topik', { exact: true }).fill('Draf balasan tertunda');
  await page.getByLabel('Pesan', { exact: true }).fill('Pesan awal sintetis untuk menguji kelanjutan draf.');
  await page.getByRole('button', { name: 'Kirim pesan', exact: true }).click();
  await expect(page.locator('#support-items')).toContainText('Draf balasan tertunda');
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/v1/templates', async route => { await gate; await route.continue(); });
  await page.reload();
  const ticket = page.locator('#support-items article').filter({ hasText: 'Draf balasan tertunda' });
  await ticket.locator('summary').click();
  const reply = ticket.getByLabel('Jawaban untuk Draf balasan tertunda');
  await reply.fill('Draf balasan tetap ada saat katalog datang.');
  release();
  await page.waitForResponse('**/api/v1/templates');
  await expect(reply).toHaveValue('Draf balasan tetap ada saat katalog datang.');
  await expect(reply).toBeFocused();
  await expect(ticket.locator('details')).toHaveAttribute('open', '');
});
