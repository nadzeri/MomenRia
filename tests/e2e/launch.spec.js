const { test, expect } = require('@playwright/test');
const path = require('node:path');

const password = 'Portrait-test-2026!';
let browserErrors;

test.beforeEach(async ({ page }) => {
  browserErrors = [];
  page.on('pageerror', error => browserErrors.push(error.message));
});
test.afterEach(async () => {
  expect(browserErrors).toEqual([]);
});

async function screenshot(page, testInfo, name) {
  await page.locator('img').evaluateAll(images => Promise.all(images.map(image => { image.loading = 'eager'; return image.decode(); })));
  await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: true });
  await testInfo.attach(name, { path: testInfo.outputPath(`${name}.png`), contentType: 'image/png' });
}
async function noOverflow(page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}
async function login(page, name) {
  await page.goto('/accounts/login/');
  await page.locator('[name="login"]').fill(`${name}@example.com`);
  await page.locator('[name="password"]').fill(password);
  await page.getByRole('button', { name: 'Masuk', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Akun saya', exact: true })).toBeVisible();
}

test('landing, catalog filters, template detail and empty-state recovery', async ({ page }, testInfo) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Lagi jauh? Foto bareng tetap bisa.' })).toBeVisible();
  await expect(page.locator('.moment-card')).toHaveCount(3);
  await noOverflow(page);
  await screenshot(page, testInfo, 'landing');
  await page.getByRole('link', { name: 'Cari template', exact: true }).first().click();
  await expect(page.locator('.moment-card')).toHaveCount(6);
  await expect(page.locator('.template-card')).toHaveCount(0);
  await screenshot(page, testInfo, 'moment-collections');
  await page.locator('.moment-card[href="#/templates/hari-raya"]').click();
  await page.getByLabel('Jumlah orang').selectOption('2');
  await page.getByLabel('Suasana').selectOption('Lebaran');
  await expect(page.locator('.template-card')).toHaveCount(1);
  await expect(page.locator('.template-card')).toContainText('Lebaran Bersama');
  await page.getByLabel('Cari template').fill('tidak-ada');
  await expect(page.getByText('Belum ada template yang cocok.')).toBeVisible();
  await page.getByRole('button', { name: 'Hapus filter' }).click();
  await expect(page.locator('.template-card')).toHaveCount(9);
  await page.getByRole('navigation', { name: 'Koleksi momen' }).getByRole('link', { name: /Kebersamaan keluarga/ }).click();
  await page.getByLabel('Suasana').selectOption('Studio');
  await expect(page.locator('.template-card')).toHaveCount(1);
  await page.getByLabel('Suasana').selectOption('');
  await screenshot(page, testInfo, 'catalog');
  await page.getByRole('link', { name: 'Momen di Rumah', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Momen di Rumah', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Pakai template ini' }).click();
  await expect(page.locator('.upload-tile')).toHaveCount(3);
  await expect(page.locator('[data-generate]')).toBeDisabled();
  await noOverflow(page);
  await screenshot(page, testInfo, 'studio');
  await page.getByRole('button', { name: 'Tambahkan foto wajah 1', exact: true }).click();
  await expect(page).toHaveURL(/accounts\/login/);
  await expect(page.getByRole('heading', { name: 'Yuk, lanjut bikin kenangan.' })).toBeVisible();
});

test('content pages, private empty library, unknown routes and payment exclusion', async ({ page }) => {
  const routes = [
    ['guide', 'Biar hasilnya oke, mulai dari fotonya.'], ['privacy', 'Kebijakan Privasi'],
    ['terms', 'Syarat dan Ketentuan'], ['support', 'Butuh bantuan? Cerita, yuk.'],
    ['projects', 'Foto saya'], ['missing-page', 'Halaman tidak ditemukan'], ['orders', 'Pembayaran belum tersedia'],
  ];
  for (const [route, heading] of routes) {
    await page.goto(`/#/${route}`);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await noOverflow(page);
  }
  await page.goto('/#/support');
  await page.getByText('Yang gratis dapat apa saja?', { exact: true }).click();
  await expect(page.getByText(/3 foto baru gratis seumur hidup per akun/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Pesanan', exact: true })).toHaveCount(0);
  await page.goto('/#/projects');
  await expect(page.getByRole('link', { name: 'Masuk ke akun' })).toBeVisible();
});

test('branded account forms validate and recovery remains reachable', async ({ page }, testInfo) => {
  await page.goto('/accounts/signup/');
  await expect(page.getByRole('heading', { name: 'Bikin akun, lalu foto bareng.' })).toBeVisible();
  await page.locator('[name="email"]').fill(`signup-${testInfo.project.name}@example.com`);
  await page.locator('[name="password1"]').fill(password);
  await page.locator('[name="password2"]').fill('Mismatch-2026!');
  await page.getByRole('button', { name: 'Buat akun', exact: true }).click();
  await expect(page.locator('.errorlist')).toBeVisible();
  await expect(page.locator('.errorlist')).not.toContainText('You must type');
  await noOverflow(page);
  await screenshot(page, testInfo, 'account');
  await page.goto('/accounts/login/');
  await page.getByRole('link', { name: 'Lupa kata sandi?' }).click();
  await expect(page.getByRole('heading', { name: 'Lupa kata sandi?' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Kirim link reset' })).toBeVisible();
});

test('complete private portrait lifecycle through real Django and synthetic worker', async ({ page, browser }, testInfo) => {
  test.setTimeout(120000);
  await login(page, testInfo.project.name);
  await page.goto('/#/templates/hari-raya');
  await page.getByRole('link', { name: 'Pilih Lebaran Bersama', exact: true }).click();
  await page.getByRole('button', { name: 'Tambahkan foto wajah 1', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByLabel('Foto JPEG atau PNG').setInputFiles({ name: 'invalid.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('not an image') });
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Cek dan pasang foto' }).click();
  await expect(page.locator('#upload-form .form-error')).toBeVisible();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByLabel('Foto JPEG atau PNG').setInputFiles(path.join(__dirname, 'generated/left.jpg'));
  await page.getByRole('button', { name: 'Cek dan pasang foto' }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(page.locator('.upload-tile.ready')).toHaveCount(1);
  await page.getByRole('button', { name: 'Tambahkan foto wajah 2', exact: true }).click();
  await page.getByLabel('Foto JPEG atau PNG').setInputFiles(path.join(__dirname, 'generated/right.jpg'));
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Cek dan pasang foto' }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.reload();
  await expect(page.locator('.upload-tile.ready')).toHaveCount(2);
  await expect(page.locator('.upload-thumbnail img')).toHaveCount(2);
  const draftUrl = page.url();
  await expect(page.locator('.face-target.ready img')).toHaveCount(2);
  await expect.poll(() => page.locator('.face-target.ready img').evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0))).toBe(true);
  await screenshot(page, testInfo, 'studio-ready');
  await page.locator('.portrait-canvas').evaluate(element => element.scrollIntoView({ block: 'center' }));
  await expect(page.locator('[data-generate]')).toBeInViewport();
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await page.screenshot({ path: testInfo.outputPath('studio-ready-viewport.png') });
  let submissions = 0;
  page.on('request', request => { if (request.method()==='POST' && /\/jobs$/.test(request.url())) submissions++; });
  await page.getByRole('button', { name: 'Buat foto keluarga' }).click({ clickCount: 2 });
  await expect(page.getByRole('heading', { name: 'Yuk, cek hasil fotomu', exact: true })).toBeVisible({ timeout: 30000 });
  expect(submissions).toBe(1);
  await expect(page.getByRole('button', { name: 'Beli versi ini' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Pesanan', exact: true })).toHaveCount(1);
  const projectUrl = page.url();
  const resultId = await page.locator('[data-greeting]').getAttribute('data-greeting');
  await page.getByRole('button', { name: 'Simpan foto', exact: true }).click();
  const downloadEvent = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download foto', exact: true }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe(`momenria-${resultId}.jpg`);
  expect(await download.failure()).toBeNull();
  await page.keyboard.press('Escape');
  const response = await page.request.get(`/api/v1/results/${resultId}/master`);
  expect(response.status()).toBe(200);
  const outsider = await browser.newContext({ baseURL: new URL(page.url()).origin });
  const outsiderPage = await outsider.newPage();
  await login(outsiderPage, 'outsider');
  expect((await outsiderPage.request.get(`/api/v1/results/${resultId}/preview?download=1`)).status()).toBe(404);
  await outsider.close();
  await page.getByRole('button', { name: 'Perbesar hasil foto', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.getByRole('button', { name: 'Semua wajah sesuai', exact: true }).click();
  await expect(page.locator('#toast')).toContainText('Semua wajah ditandai sesuai');
  await page.getByRole('button', { name: 'Tambah ucapan', exact: true }).click();
  await page.getByLabel('Ucapan', { exact: true }).fill('Selalu dekat di hati');
  await page.getByRole('button', { name: 'Simpan versi baru' }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Versi 2 · Ucapan', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Versi 1', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Versi 1', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.locator('[data-correct]').first().click();
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Mulai koreksi', exact: true }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Versi 3', exact: true })).toBeVisible({ timeout: 30000 });
  await expect(page.locator('[data-correct]').first()).toBeEnabled();
  await page.locator('[data-correct]').nth(1).click();
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Mulai koreksi', exact: true }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Versi 4', exact: true })).toBeVisible({ timeout: 30000 });
  await expect(page.locator('[data-correct]').nth(1)).toBeEnabled();
  await page.getByRole('link', { name: 'Buat versi baru', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Buat foto keluarga' })).toBeEnabled();
  await page.getByRole('button', { name: 'Buat foto keluarga' }).click({ clickCount: 2 });
  await expect(page.getByRole('button', { name: 'Versi 5', exact: true })).toBeVisible({ timeout: 30000 });
  expect(submissions).toBe(2);
  await noOverflow(page);
  await screenshot(page, testInfo, 'result');
  await page.getByRole('link', { name: 'Bantuan untuk proyek ini' }).click();
  await page.getByLabel('Topik', { exact: true }).fill('Cek hasil keluarga');
  await page.getByLabel('Pesan', { exact: true }).fill('Saya ingin meminta bantuan untuk memeriksa hasil foto ini.');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Kirim pesan' }).click();
  await expect(page.getByRole('heading', { name: 'Cek hasil keluarga', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Cabut akses gambar' }).click();
  await expect(page.getByRole('button', { name: 'Cabut akses gambar' })).toHaveCount(0);
  await page.goto(draftUrl);
  await expect(page.getByRole('button', { name: 'Ganti template', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Buat foto keluarga' })).toBeEnabled();
  await page.goto(projectUrl);
  await page.getByRole('button', { name: 'Hapus proyek', exact: true }).click();
  await page.getByLabel('Kata sandi', { exact: true }).fill(password);
  await page.getByRole('checkbox').check();
  await page.getByRole('dialog').getByRole('button', { name: 'Hapus proyek', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Belum ada foto. Bikin yang pertama, yuk!', exact: true })).toBeVisible();
  expect((await page.request.get(`/api/v1/results/${resultId}/preview`)).status()).toBe(404);
});

test('slow support response cannot overwrite another route', async ({ page }, testInfo) => {
  await login(page, testInfo.project.name);
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/v1/support/tickets', async route => {
    await gate;
    await route.continue();
  });
  await page.goto('/#/support');
  await expect(page.getByLabel('Pesan', { exact: true })).toBeVisible();
  await page.getByLabel('Pesan', { exact: true }).fill('Tulisan saya harus tetap tersimpan di formulir.');
  await page.getByRole('link', { name: 'Template', exact: true }).click();
  release();
  await expect(page.getByLabel('Cari template')).toBeVisible();
  await expect(page.locator('.moment-card')).toHaveCount(6);
});

test('keyboard navigation and narrow enlarged layout keep controls reachable', async ({ page }) => {
  await page.goto('/#/templates');
  await expect(page.getByLabel('Cari template')).toBeVisible();
  await page.getByLabel('Cari template').focus();
  await page.keyboard.type('lebaran');
  await expect(page.locator('.template-card')).toHaveCount(1);
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Jumlah orang')).toBeFocused();
  await page.setViewportSize({ width: 360, height: 780 });
  await page.evaluate(() => document.documentElement.style.fontSize = '24px');
  await noOverflow(page);
  await page.getByRole('link', { name: 'Pilih Lebaran Bersama', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Tambahkan foto wajah 1', exact: true })).toBeVisible();
  await noOverflow(page);
});

test('paused catalog, uncertain jobs and expired results have usable recovery states', async ({ page }, testInfo) => {
  await login(page, testInfo.project.name);
  const catalog = await (await page.request.get('/api/v1/templates')).json();
  const template = { ...catalog.items[0], status: 'paused' };
  const project = {
    id: '11111111-1111-4111-8111-111111111111', template_id: template.id, template,
    state: 'active', revision: 3, assignments: {}, sources: [], correction_available: true,
    selected_result_id: '22222222-2222-4222-8222-222222222222',
    results: [{ id: '22222222-2222-4222-8222-222222222222', number: 1, kind: 'creation', status: 'ready', greeting: '', synthetic: true, expires_at: new Date(Date.now()+86400000).toISOString(), references: [{ status: 'expired', expires_at: '2020-01-01T00:00:00Z', thumbnail_url: null }], output: null }],
    jobs: [{ id: '33333333-3333-4333-8333-333333333333', state: 'uncertain', operation: 'correction', error_code: '' }],
  };
  await page.route('**/api/v1/templates', route => route.fulfill({ json: { ...catalog, items: [] } }));
  await page.route('**/api/v1/projects', route => route.fulfill({ json: { items: [project] } }));
  await page.route(`**/api/v1/projects/${project.id}`, route => route.fulfill({ json: project }));
  await page.route(`**/api/v1/results/${project.selected_result_id}/preview`, route => route.fulfill({ path: path.join(__dirname, '../../static/app/assets/home.webp'), contentType: 'image/webp' }));
  await page.goto(`/#/project/${project.id}`);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Yuk, cek hasil fotomu', exact: true })).toBeVisible();
  await expect(page.getByText('Masih menunggu kabar', { exact: true })).toBeVisible();
  await expect(page.getByText('Masa simpan foto asli sudah habis atau fotonya sudah dihapus.', { exact: true })).toBeVisible();
  await expect(page.locator('[data-correct]').first()).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Simpan foto', exact: true })).toBeVisible();
  await page.goto(`/#/support/${project.id}`);
  await page.getByLabel('Pesan', { exact: true }).fill('Tulisan tetap ada ketika proses latar diperbarui.');
  const refresh = page.waitForRequest(request => /\/api\/v1\/projects$/.test(request.url()));
  await refresh;
  await expect(page.getByLabel('Pesan', { exact: true })).toHaveValue('Tulisan tetap ada ketika proses latar diperbarui.');
  project.results[0].expires_at = '2020-01-01T00:00:00Z';
  project.jobs = [];
  await page.goto(`/#/project/${project.id}`);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Hasil sudah kedaluwarsa', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Simpan foto', exact: true })).toHaveCount(0);
});

test('startup failure offers retry and service pause blocks generation', async ({ page }) => {
  await page.route('**/api/v1/templates', route => route.fulfill({ status: 503, json: { message: 'Koleksi sedang diperbarui.' } }));
  await page.goto('/');
  await expect(page.locator('#connection-status')).toContainText('Koleksi sedang diperbarui.');
  await expect(page.getByRole('heading', { name: 'Lagi jauh? Foto bareng tetap bisa.' })).toBeVisible();
  await page.unroute('**/api/v1/templates');
  await page.getByRole('button', { name: 'Coba hubungkan lagi' }).click();
  await expect(page.locator('.collection-section .moment-card')).toHaveCount(3);
  await page.route('**/api/v1/templates', async route => {
    const response = await route.fetch();
    const catalog = await response.json();
    await route.fulfill({ json: { ...catalog, admission_enabled: false } });
  });
  await page.goto('/#/templates/hari-raya');
  await page.reload();
  await page.getByRole('link', { name: 'Pilih Lebaran Bersama', exact: true }).click();
  await expect(page.getByText(/Bikin foto lagi dijeda/)).toBeVisible();
  await expect(page.locator('[data-generate]')).toBeDisabled();
  await page.locator('.skip').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main')).toBeFocused();
  await expect(page).toHaveURL(/#\/studio\//);
});

async function stubRetryableDraft(page, account) {
  await login(page, account);
  const catalog = await (await page.request.get('/api/v1/templates')).json();
  const template = catalog.items.find(item => item.people_count === 2);
  const session = await (await page.request.get('/api/v1/session')).json();
  const sources = template.slots.map((slot,index) => ({ id: `source-${index}`, status: 'ready', expires_at: new Date(Date.now()+86400000).toISOString() }));
  const project = { id: '44444444-4444-4444-8444-444444444444', template_id: template.id, template, revision: 3, state: 'draft', sources, assignments: Object.fromEntries(template.slots.map((slot,index)=>[slot.id,sources[index].id])), results: [], jobs: [], correction_available: true };
  await page.route('**/api/v1/session', route => route.fulfill({ json: { ...session, creation_available: true } }));
  await page.route('**/api/v1/projects', route => route.fulfill({ json: { items: [project] } }));
  await page.route(`**/api/v1/projects/${project.id}`, route => route.fulfill({ json: project }));
  await page.goto(`/#/studio/${template.id}/${project.id}`);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Buat foto keluarga' })).toBeEnabled();
  return project;
}

test('confirmed failed generation can retry with a new request identity', async ({ page }, testInfo) => {
  const project = await stubRetryableDraft(page, testInfo.project.name);
  const keys = [];
  await page.route(`**/api/v1/projects/${project.id}/jobs`, route => {
    keys.push(route.request().headers()['idempotency-key']);
    project.jobs = [{ id: 'failed-job', operation: 'creation', state: 'failed', error_code: 'provider_unavailable' }];
    return route.fulfill({ status: 202, json: { id: `attempt-${keys.length}`, state: 'queued' } });
  });
  await page.getByRole('button', { name: 'Buat foto keluarga' }).click();
  await page.getByRole('link', { name: 'Lanjutkan draf', exact: true }).click();
  await page.getByRole('button', { name: 'Buat foto keluarga' }).click();
  await expect.poll(() => keys.length).toBe(2);
  expect(keys[1]).not.toBe(keys[0]);
});

test('delayed generation cannot pull users away from their support draft', async ({ page }, testInfo) => {
  const project = await stubRetryableDraft(page, testInfo.project.name);
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route(`**/api/v1/projects/${project.id}/jobs`, async route => {
    await gate;
    await route.fulfill({ status: 202, json: { id: 'delayed-job', state: 'queued' } });
  });
  await page.getByRole('button', { name: 'Buat foto keluarga' }).click();
  await page.getByRole('link', { name: 'Bantuan', exact: true }).first().click();
  await page.getByLabel('Pesan', { exact: true }).fill('Saya sedang menulis permintaan bantuan.');
  const refresh = page.waitForResponse(response => /\/api\/v1\/projects$/.test(response.url()));
  release();
  await refresh;
  await expect(page.locator('#toast')).toContainText('Foto masuk antrean');
  await expect(page.getByLabel('Pesan', { exact: true })).toHaveValue('Saya sedang menulis permintaan bantuan.');
  await expect(page).toHaveURL(/#\/support$/);
});

test('support fields cannot accept unsaved edits while submission is pending', async ({ page }, testInfo) => {
  await login(page, testInfo.project.name);
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/v1/support/tickets', async route => {
    if (route.request().method()==='POST') await gate;
    await route.continue();
  });
  await page.goto('/#/support');
  await page.getByLabel('Topik', { exact: true }).fill('Permintaan lambat');
  const message = page.getByLabel('Pesan', { exact: true });
  await message.fill('Pesan asli yang harus tersimpan.');
  await page.getByRole('button', { name: 'Kirim pesan' }).click();
  try {
    await message.focus();
    await page.keyboard.type(' Perubahan yang belum terkirim.');
    expect(await message.inputValue()).toBe('Pesan asli yang harus tersimpan.');
  } finally { release(); }
  await expect(page.getByRole('heading', { name: 'Permintaan lambat', exact: true })).toBeVisible();
});


test('event and university filters lead into a complete solo graduation portrait', async ({ page }, testInfo) => {
  test.setTimeout(90000);
  await login(page, `graduate-${testInfo.project.name}`);
  await page.goto('/#/templates');
  await page.locator('.moment-card[href="#/templates/wisuda"]').click();
  await expect(page.locator('.template-card')).toHaveCount(8);
  await page.getByRole('combobox', { name: 'Universitas', exact: true }).selectOption('Universitas Indonesia');
  await page.getByLabel('Jumlah orang').selectOption('1');
  await expect(page.locator('.template-card')).toHaveCount(1);
  await page.getByLabel('Cari template').fill('Crystal of Knowledge');
  await expect(page.locator('.template-card')).toHaveCount(1);
  await noOverflow(page);
  await screenshot(page, testInfo, 'graduation-catalog');
  await page.getByRole('link', { name: 'Wisuda UI', exact: true }).click();
  await expect(page.getByText('Latar dan toganya ilustrasi AI, ya. Ini bukan foto lokasi asli atau template resmi kampus.')).toBeVisible();
  await page.getByRole('link', { name: 'Pakai template ini' }).click();
  await expect(page.locator('.upload-tile')).toHaveCount(1);
  await page.getByRole('button', { name: 'Tambahkan foto wajah 1', exact: true }).click();
  await page.getByLabel('Foto JPEG atau PNG').setInputFiles(path.join(__dirname, 'generated/left.jpg'));
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Cek dan pasang foto' }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.getByRole('button', { name: /Buat potret gratis/ }).click();
  await expect(page.locator('.result-image img')).toBeVisible({ timeout: 60000 });
  await screenshot(page, testInfo, 'solo-graduation-result');
  await page.getByRole('link', { name: 'Template', exact: true }).click();
  await page.getByLabel('Cari template').fill('tidak-ada');
  await page.getByRole('button', { name: 'Hapus filter' }).click();
  await expect(page.locator('.moment-card')).toHaveCount(6);
  await expect(page.getByRole('combobox', { name: 'Universitas', exact: true })).toHaveCount(0);
  await page.locator('.moment-card[href="#/templates/si-kecil"]').click();
  await page.getByLabel('Suasana').selectOption('Bayi');
  await expect(page.locator('.template-card')).toHaveCount(2);
  await page.getByRole('navigation', { name: 'Koleksi momen' }).getByRole('link', { name: /Cerita cinta/ }).click();
  await page.getByLabel('Suasana').selectOption('Pre-wedding');
  await expect(page.locator('.template-card')).toHaveCount(2);
  await noOverflow(page);
});

test('studio switches within one draft and reuses saved photos after confirmation', async ({ page }, testInfo) => {
  await login(page, testInfo.project.name);
  const catalog = await (await page.request.get('/api/v1/templates')).json();
  const lebaran = catalog.items.find(item => item.slug === 'lebaran');
  const home = catalog.items.find(item => item.slug === 'home');
  const initialProjects = (await (await page.request.get('/api/v1/projects')).json()).items.length;
  await page.goto(`/#/studio/${lebaran.id}`);
  await page.getByRole('button', { name: 'Ganti template', exact: true }).click();
  await page.getByRole('button', { name: 'Kebersamaan keluarga', exact: true }).click();
  await expect(page.locator('.picker-template')).toHaveCount(2);
  await page.getByRole('button', { name: 'Pilih Momen di Rumah', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`studio/${home.id}$`));
  await expect(page.locator('.upload-tile')).toHaveCount(3);
  expect((await (await page.request.get('/api/v1/projects')).json()).items.length).toBe(initialProjects);
  await page.getByRole('button', { name: 'Tambahkan foto wajah 1', exact: true }).click();
  await page.getByLabel('Foto JPEG atau PNG').setInputFiles(path.join(__dirname, 'generated/left.jpg'));
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Cek dan pasang foto' }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  const projectId = page.url().split('/').at(-1);
  const before = await (await page.request.get(`/api/v1/projects/${projectId}`)).json();
  await page.getByRole('button', { name: 'Ganti template', exact: true }).click();
  await page.getByRole('button', { name: 'Hari raya & perayaan', exact: true }).click();
  await expect(page.locator('.picker-template')).toHaveCount(9);
  await noOverflow(page);
  await screenshot(page, testInfo, 'studio-template-picker');
  await page.getByRole('button', { name: 'Pilih Lebaran Bersama', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Penempatan 1 wajah akan dikosongkan.');
  await page.keyboard.press('Escape');
  await expect(page.locator('.upload-tile.ready')).toHaveCount(1);
  expect((await (await page.request.get(`/api/v1/projects/${projectId}`)).json()).template_id).toBe(home.id);
  await page.getByRole('button', { name: 'Ganti template', exact: true }).click();
  await page.getByRole('button', { name: 'Hari raya & perayaan', exact: true }).click();
  await page.getByRole('button', { name: 'Pilih Lebaran Bersama', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Ganti template', exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page).toHaveURL(new RegExp(`studio/${lebaran.id}/${projectId}$`));
  await expect(page.locator('.upload-tile')).toHaveCount(2);
  await expect(page.locator('.upload-tile.ready')).toHaveCount(0);
  const changed = await (await page.request.get(`/api/v1/projects/${projectId}`)).json();
  expect(changed.sources.map(item => item.id)).toEqual(before.sources.map(item => item.id));
  expect(changed.assignments).toEqual({});
  await page.reload();
  await page.getByRole('button', { name: 'Tambahkan foto wajah 2', exact: true }).click();
  await expect(dialog.getByRole('heading', { name: 'Foto tersimpan' })).toBeVisible();
  const assignmentUrl = `**/api/v1/projects/${projectId}/slots/${lebaran.slots[1].id}`;
  await page.route(assignmentUrl, route => route.fulfill({ status: 503, json: { message: 'Foto belum bisa dipasangkan. Coba lagi.' } }));
  await page.getByRole('button', { name: 'Gunakan foto tersimpan 1', exact: true }).click();
  await expect(dialog.locator('.form-error')).toContainText('Foto belum bisa dipasangkan. Coba lagi.');
  await page.unroute(assignmentUrl);
  await page.getByRole('button', { name: 'Gunakan foto tersimpan 1', exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator('.upload-tile.ready')).toHaveCount(1);
  await page.reload();
  await expect(page.locator('.upload-tile.ready')).toHaveCount(1);
  expect((await (await page.request.get(`/api/v1/projects/${projectId}`)).json()).assignments[lebaran.slots[1].id]).toBe(before.sources[0].id);
  await screenshot(page, testInfo, 'studio-template-changed');

  await page.getByRole('button', { name: 'Ganti template', exact: true }).click();
  await page.getByRole('button', { name: 'Kebersamaan keluarga', exact: true }).click();
  await page.getByRole('button', { name: 'Pilih Momen di Rumah', exact: true }).click();
  const session = await (await page.request.get('/api/v1/session')).json();
  const current = await (await page.request.get(`/api/v1/projects/${projectId}`)).json();
  const otherTab = await page.request.post(`/api/v1/projects/${projectId}/undo`, {
    headers: { 'X-CSRFToken': session.csrf_token }, data: { expected_revision: current.revision }
  });
  expect(otherTab.ok()).toBe(true);
  await dialog.getByRole('button', { name: 'Ganti template', exact: true }).click();
  await expect(dialog.locator('.form-error')).toContainText('Draf berubah di tab lain.');
  expect((await (await page.request.get(`/api/v1/projects/${projectId}`)).json()).template_id).toBe(lebaran.id);
  await dialog.getByRole('button', { name: 'Pilih yang lain' }).click();
  await page.getByRole('button', { name: 'Pilih Momen di Rumah', exact: true }).click();
  await dialog.getByRole('button', { name: 'Ganti template', exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator('.upload-tile')).toHaveCount(3);
});
