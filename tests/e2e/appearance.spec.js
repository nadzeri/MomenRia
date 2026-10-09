const { test, expect } = require('@playwright/test');

test('navigation and page layouts fit from compact mobile to wide desktop', async ({ page }, testInfo) => {
  const widths = testInfo.project.name === 'mobile' ? [360, 390, 430] : [600, 820, 1024, 1366, 1440, 1920];
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Lagi jauh?');
  await expect(page.locator('#app-nav')).toHaveCount(1);
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    for (const [label, heading] of [['Beranda', 'Lagi jauh?'], ['Template', 'Mau simpan momen apa?'], ['Panduan', 'Biar hasilnya oke, mulai dari fotonya.']]) {
      const link = page.getByRole('navigation', { name: 'Navigasi utama' }).getByRole('link', { name: label, exact: true });
      await link.click();
      await expect(link).toHaveAttribute('aria-current', 'page');
      await expect(page.getByRole('heading', { level: 1 })).toContainText(heading);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    }
    expect(await page.locator('.nav-link').evaluateAll(links => links.every(link => {
      const bounds = link.getBoundingClientRect();
      return bounds.width >= 44 && bounds.height >= 44;
    }))).toBe(true);
  }
});
