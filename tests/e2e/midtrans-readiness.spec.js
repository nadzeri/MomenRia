const { test, expect } = require('@playwright/test');

test('public policies and contact work without JavaScript', async ({ browser, baseURL }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, baseURL });
  const page = await context.newPage();
  for (const [path, heading] of [
    ['/terms/', 'Syarat dan Ketentuan'], ['/privacy/', 'Kebijakan Privasi'],
    ['/refunds/', 'Kebijakan Pengembalian Dana'], ['/contact/', 'Hubungi Kami'],
  ]) {
    await page.goto(path);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await expect(page.locator('footer a[href="mailto:support@momenria.id"]')).toBeVisible();
    await expect(page.locator('footer a[href="tel:+6282226669926"]')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  await context.close();
});

test('legacy policy routes resolve even when the catalog fails', async ({ page }) => {
  await page.route('**/api/v1/templates', route => route.abort());
  await page.goto('/#/terms');
  await expect(page).toHaveURL(/\/terms\/$/);
  await expect(page.getByRole('heading', { name: 'Syarat dan Ketentuan', exact: true })).toBeVisible();
  await page.goto('/#/privacy');
  await expect(page).toHaveURL(/\/privacy\/$/);
  await page.goto('/');
  await expect(page.locator('footer a[href="/refunds/"]')).toBeVisible();
  await expect(page.locator('footer a[href="/contact/"]')).toBeVisible();
});
