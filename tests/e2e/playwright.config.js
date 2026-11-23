// Playwright configuration for the VigilOps browser tests.
//
//   docker compose up --build -d          (from the repository root)
//   cd tests/e2e
//   npm install
//   npx playwright install chromium
//   npx playwright test
//
// The tests drive a real browser against the running stack and sign in with
// the bootstrap accounts from the repository's .env file.
const { defineConfig, devices } = require('@playwright/test');
const { env } = require('./support/env');

module.exports = defineConfig({
  testDir: './specs',
  // The tests share one running platform and build on each other's state.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  outputDir: 'test-results',
  use: {
    baseURL: process.env.BASE_URL || `http://localhost:${env.VIGILOPS_HTTP_PORT || '8080'}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    viewport: { width: 1360, height: 850 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1360, height: 850 } } }],
});
