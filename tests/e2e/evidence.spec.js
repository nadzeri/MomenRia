const { test, expect } = require('@playwright/test');

test('public controls remain usable while private startup is pending', async ({ page }, testInfo) => {
  await page.goto('/accounts/login/');
  await page.locator('[name="login"]').fill(`competitive-${testInfo.project.name}@example.com`);
  await page.locator('[name="password"]').fill('Portrait-test-2026!');
  await page.getByRole('button', { name: 'Masuk', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Akun saya', exact: true })).toBeVisible();
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/v1/projects', async route => { await gate; await route.continue(); });
  await page.goto('/#/guide');
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Biar hasilnya oke, mulai dari fotonya.' })).toBeVisible();
  await page.getByRole('link', { name: 'Pilih template pertamamu', exact: true }).click();
  await expect(page.getByLabel('Cari template')).toBeVisible();
  await page.getByLabel('Cari template').fill('wisuda ui');
  await expect(page.getByRole('link', { name: 'Wisuda UI', exact: true })).toBeVisible();
  release();
  await page.waitForResponse('**/api/v1/projects');
  await expect(page.getByLabel('Cari template')).toHaveValue('wisuda ui');
});

test('critical-path lab trace records cold startup and catalog interaction', async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.auditLongTasks = [];
    window.auditLongTasksSupported = PerformanceObserver.supportedEntryTypes.includes('longtask');
    if (window.auditLongTasksSupported) new PerformanceObserver(list => {
      window.auditLongTasks.push(...list.getEntries().map(entry => ({ start: entry.startTime, duration: entry.duration, name: entry.name })));
    }).observe({ type: 'longtask', buffered: true });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Lagi jauh? Foto bareng tetap bisa.' })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await expect.poll(() => page.locator('.hero-photo img').evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0))).toBe(true);
  await page.getByRole('link', { name: 'Cari template', exact: true }).click();
  await page.getByLabel('Cari template').fill('wisuda ui');
  await page.getByRole('link', { name: 'Wisuda UI', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Wisuda UI', exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByLabel('Cari template')).toHaveValue('wisuda ui');
  const metrics = await page.evaluate(() => ({
    setup: 'Localhost, fresh browser context, no CPU or network throttling; synthetic catalog',
    navigation: performance.getEntriesByType('navigation').map(entry => ({ responseEnd: entry.responseEnd, domContentLoaded: entry.domContentLoadedEventEnd, load: entry.loadEventEnd })),
    resources: performance.getEntriesByType('resource').map(entry => ({ name: new URL(entry.name).pathname, transferSize: entry.transferSize, duration: entry.duration })),
    longTasksSupported: window.auditLongTasksSupported,
    longTasks: window.auditLongTasks,
  }));
  await testInfo.attach('critical-path-lab.json', { body: JSON.stringify(metrics, null, 2), contentType: 'application/json' });
  require('node:fs').writeFileSync(testInfo.outputPath('critical-path-lab.json'), JSON.stringify(metrics, null, 2));
  if (testInfo.project.name === 'desktop') {
    expect(metrics.longTasksSupported).toBe(true);
    expect(metrics.longTasks).toEqual([]);
  }
  expect(metrics.resources.reduce((total, entry) => total + entry.transferSize, 0)).toBeLessThan(2000000);
});

test('twofold text enlargement retains guidance, forms and navigation', async ({ page }, testInfo) => {
  for (const path of ['/#/guide', '/#/support', '/accounts/login/']) {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await page.evaluate(() => {
      const styles = [...document.querySelectorAll('body,body *')].map(element => {
        const style = getComputedStyle(element);
        return { element, size: parseFloat(style.fontSize), line: parseFloat(style.lineHeight) };
      });
      for (const { element, size, line } of styles) {
        element.style.fontSize = `${size * 2}px`;
        if (Number.isFinite(line)) element.style.lineHeight = `${line * 2}px`;
      }
    });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    const controls = page.locator('button:visible,input:visible,textarea:visible,select:visible,nav a:visible');
    for (const control of await controls.all()) {
      const bounds = await control.evaluate(element => {
        const target = element.matches('input[type=checkbox],input[type=radio]') ? element.labels[0] || element : element;
        const box = target.getBoundingClientRect();
        return { width: box.width, height: box.height };
      });
      expect(bounds.width).toBeGreaterThan(0);
      expect(bounds.height).toBeGreaterThanOrEqual(24);
    }
    if (path === '/#/support') {
      await page.getByLabel('Email yang bisa dihubungi').fill('enlarged@example.com');
      await page.getByLabel('Pesan', { exact: true }).fill('Pesan contoh dapat diisi dengan teks yang diperbesar.');
      await expect(page.getByRole('button', { name: 'Kirim permintaan akun' })).toBeVisible();
    }
    await page.screenshot({ path: testInfo.outputPath(`${path.includes('guide') ? 'guide' : path.includes('support') ? 'support' : 'login'}-text-200.png`), fullPage: true });
  }
});
