const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 10000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:8765',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile', use: { ...devices['iPhone 13'], baseURL: 'http://127.0.0.1:8767' } },
  ],
  webServer: [8765, 8767].map(port => ({
    command: `.venv/bin/python tests/e2e/server.py --port ${port}`,
    url: `http://127.0.0.1:${port}/health/ready`,
    reuseExistingServer: false,
    timeout: 60000,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 5000 },
  })),
});
