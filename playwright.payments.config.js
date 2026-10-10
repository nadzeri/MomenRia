const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e', testMatch: 'payments.spec.js', workers: 1, fullyParallel: false,
  outputDir: './test-results-payments',
  timeout: 120000, expect: { timeout: 10000 }, reporter: [['list']],
  use: { trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 }, baseURL: 'http://127.0.0.1:8775' } },
    { name: 'mobile', use: { ...devices['iPhone 13'], baseURL: 'http://127.0.0.1:8777' } },
  ],
  webServer: [8775, 8777].map(port => ({
    command: `.venv/bin/python tests/e2e/server.py --payments --port ${port}`,
    url: `http://127.0.0.1:${port}/health/ready`, reuseExistingServer: false, timeout: 60000,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 5000 },
  })),
});
