const { test, expect } = require('@playwright/test');
const path = require('node:path');

test('mocked QRIS stays on-site and renders uncertain, queued, failed and refunded states', async ({ page }, testInfo) => {
  await page.goto('/accounts/login/');
  await page.locator('[name="login"]').fill(`paymentstates-${testInfo.project.name}@example.com`);
  await page.locator('[name="password"]').fill('Portrait-test-2026!');
  await page.getByRole('button', { name: 'Masuk', exact: true }).click();
  const id = 'b374c06e-bec7-4343-9485-0f5dc808f54c';
  const qr = 'https://api.sandbox.midtrans.com/v2/qris/ui-test/qr-code';
  let order = { id, merchant_reference: 'MR-UI-SIMULATION', purpose: 'generation', amount: 9900, currency: 'IDR', project_id: null, result_id: null, download_url: null, refunds: [], payment_state: 'pending', job_state: 'awaiting_payment', fulfillment_state: 'unavailable', expires_at: new Date(Date.now()+900000).toISOString(), payment_instructions: { kind: 'qris', qr_url: qr, message: 'Instruksi QR simulasi, bukan tagihan.' } };
  await page.route(`**/api/v1/orders/${id}`, route => route.fulfill({ json: order }));
  await page.route(qr, route => route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240"><rect width="240" height="240" fill="white"/><rect x="20" y="20" width="200" height="200" fill="none" stroke="black"/><text x="120" y="120" text-anchor="middle">QR SIMULASI</text></svg>' }));
  await page.route('**/', async route => {
    const response = await route.fetch(), headers = response.headers();
    if (headers['content-security-policy']) headers['content-security-policy'] = headers['content-security-policy'].replace(/img-src[^;]+/, value => value+' https://api.sandbox.midtrans.com');
    await route.fulfill({ response, headers });
  });
  await page.goto(`/#/orders/${id}`);
  await page.reload();
  await expect(page.locator('#orders-list')).toContainText('Menunggu pembayaran');
  await expect(page.getByRole('img', { name: 'Kode QRIS pembayaran MR-UI-SIMULATION' })).toHaveAttribute('src', qr);
  await expect.poll(() => page.locator('.payment-qr').evaluate(image => image.complete && image.naturalWidth===240)).toBe(true);
  await expect(page.getByRole('button', { name: 'Simulasikan pembayaran' })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('mocked-qris.png'), fullPage: true });
  for (const [payment, job, refunds, label] of [
    ['uncertain','awaiting_payment',[],'Status pembayaran belum pasti'],
    ['paid','queued',[],'Dalam antrean'],
    ['paid','failed',[{ state:'processing', amount_idr:9900 }],'Sedang diproses'],
    ['paid','cancelled',[{ state:'succeeded', amount_idr:9900 }],'Dana dikembalikan'],
  ]) {
    order = { ...order, payment_state:payment, job_state:job, refunds };
    await page.reload();
    await expect(page.locator('#orders-list')).toContainText(label);
    expect(new URL(page.url()).hostname).toBe('127.0.0.1');
    if(payment==='paid') await expect(page.locator('.payment-qr')).toHaveCount(0);
  }
  order = { ...order, payment_state:'paid', job_state:'cancelled', fulfillment_state:'delivery_failed', refunds:[], refund_observed_idr:990, refund_remaining_idr:8910 };
  await page.reload();
  await expect(page.locator('#orders-list')).toContainText('Pengembalian sebagian terkonfirmasi: Rp990');
  await expect(page.locator('#orders-list')).toContainText('Sisa pembayaran Rp8.910');
  await expect(page.locator('.payment-qr')).toHaveCount(0);
});

test('three lifetime free pictures, one paid creation, recovery and order-linked support', async ({ page, browser }, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/accounts/login/');
  await page.locator('[name="login"]').fill(`payments-${testInfo.project.name}@example.com`);
  await page.locator('[name="password"]').fill('Portrait-test-2026!');
  await page.getByRole('button', { name: 'Masuk', exact: true }).click();
  await page.goto('/#/templates/hari-raya');
  await page.getByRole('link', { name: 'Pilih Lebaran Bersama', exact: true }).click();
  await page.getByRole('button', { name: 'Tambahkan foto wajah 1', exact: true }).click();
  await page.locator('[name="image"]').setInputFiles(path.join(__dirname, 'generated/left.jpg'));
  await page.locator('[name="consent"]').check();
  await page.getByRole('button', { name: 'Cek dan pasang foto', exact: true }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.getByRole('button', { name: 'Tambahkan foto wajah 2', exact: true }).click();
  await page.locator('[name="image"]').setInputFiles(path.join(__dirname, 'generated/right.jpg'));
  await page.locator('[name="consent"]').check();
  await page.getByRole('button', { name: 'Cek dan pasang foto', exact: true }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  for (let used = 0; used < 3; used++) {
    await expect(page.locator('[data-generate]')).toContainText(`tersisa ${3-used}`);
    await page.locator('[data-generate]').click();
    await expect(page.getByRole('heading', { name: 'Yuk, cek hasil fotomu', exact: true })).toBeVisible({ timeout: 30000 });
    await expect.poll(async () => (await (await page.request.get('/api/v1/session')).json()).pricing.free_used, { timeout: 30000 }).toBe(used + 1);
    await page.reload();
    if (used < 2) await page.getByRole('link', { name: 'Buat versi baru' }).click();
  }
  const projectId = page.url().split('/').at(-1);
  await page.getByRole('link', { name: 'Buat versi baru' }).click();
  await page.route('**/api/v1/session', async route => {
    const response = await route.fetch(), session = await response.json();
    await route.fulfill({ response, json: { ...session, pricing: { ...session.pricing, checkout_enabled: false } } });
  });
  await page.reload();
  await expect(page.locator('[data-generate]')).toBeDisabled();
  await expect(page.locator('.generation-hint')).toContainText('Pembayaran foto baru sedang dijeda');
  await expect(page.getByRole('link', { name: 'Pesanan', exact: true })).toBeVisible();
  await page.unroute('**/api/v1/session');
  await page.reload();
  await expect(page.locator('[data-generate]')).toContainText('Lanjut bayar Rp9.900');
  await page.locator('[data-generate]').click();
  await expect(page.getByRole('dialog')).toContainText('Rp9.900');
  const acknowledgement = page.getByLabel(/Aku menyetujui/);
  await expect(acknowledgement).not.toBeChecked();
  await expect(page.getByRole('dialog').getByRole('link', { name: 'Ketentuan' })).toHaveAttribute('href', '/terms/');
  await acknowledgement.check();
  let attempts = 0;
  await page.route('**/generation-orders', async route => {
    attempts++;
    if (attempts > 1) return route.continue();
    await route.fetch();
    await route.abort('connectionreset');
  });
  await page.getByRole('button', { name: 'Konfirmasi & bayar Rp9.900' }).click();
  await expect(page.locator('#purchase-form .form-error')).toContainText('Koneksi putus');
  await page.getByRole('button', { name: 'Konfirmasi & bayar Rp9.900' }).click();
  await expect(page.getByRole('heading', { name: 'Pesanan', exact: true })).toBeVisible();
  const response = await (await page.request.get('/api/v1/orders')).json();
  expect(response.items).toHaveLength(1);
  const order = response.items[0];
  expect(order.amount).toBe(9900);
  expect(order.job_state).toBe('awaiting_payment');
  expect(order.result_id).toBeNull();
  await page.reload();
  await expect(page.locator('#orders-list')).toContainText('Menunggu pembayaran');
  await expect(page.locator('#orders-list')).toContainText('tidak ada uang yang ditagih');
  await page.getByRole('button', { name: 'Simulasikan pembayaran' }).click();
  await expect(page.locator('#orders-list')).toContainText('Pembayaran berhasil');
  await page.goto(`/#/project/${projectId}`);
  await expect.poll(async () => (await (await page.request.get(`/api/v1/projects/${projectId}`)).json()).results.length, { timeout: 30000 }).toBe(4);
  await page.reload();
  await page.getByRole('button', { name: 'Simpan foto', exact: true }).click();
  await expect(page.getByLabel('Format foto')).toContainText('2048 × 1536 px');
  const downloaded = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download foto', exact: true }).click();
  expect(await (await downloaded).failure()).toBeNull();
  await page.keyboard.press('Escape');
  await page.goto(`/#/orders/${order.id}`);
  await page.getByRole('link', { name: 'Bantuan / pengembalian dana' }).click();
  await page.getByLabel('Topik', { exact: true }).fill('Permintaan pengembalian dana');
  await page.getByLabel('Pesan', { exact: true }).fill('Saya memerlukan bantuan untuk pesanan foto yang sudah dibayar.');
  await page.getByRole('button', { name: 'Kirim pesan' }).click();
  await expect(page.locator('#support-items')).toContainText('Permintaan pengembalian dana');
  const tickets = await (await page.request.get('/api/v1/support/tickets')).json();
  expect(tickets.items[0].order_id).toBe(order.id);
  const outsider = await browser.newContext({ baseURL: new URL(page.url()).origin });
  const otherPage = await outsider.newPage();
  await otherPage.goto('/accounts/login/');
  await otherPage.locator('[name="login"]').fill('outsider@example.com');
  await otherPage.locator('[name="password"]').fill('Portrait-test-2026!');
  await otherPage.getByRole('button', { name: 'Masuk', exact: true }).click();
  expect((await otherPage.request.get(`/api/v1/orders/${order.id}`)).status()).toBe(404);
  await outsider.close();
  await page.goto(`/#/orders/${order.id}`);
  await page.screenshot({ path: testInfo.outputPath('paid-order.png'), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  expect(errors).toEqual([]);
});
