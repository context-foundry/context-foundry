import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E Test Configuration for Context Foundry Dashboard
 *
 * Tests run against the Vite dev server (or production build).
 * The daemon API is mocked for isolated testing.
 */

// Allow port to be configured via environment variable
const PORT = process.env.DASHBOARD_PORT || '5173';
const BASE_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],

  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    // Mobile viewports
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    },
  ],

  // Start dev server before tests (skip if already running)
  webServer: process.env.SKIP_WEBSERVER
    ? undefined
    : {
        command: `npm run dev -- --port ${PORT}`,
        url: BASE_URL,
        reuseExistingServer: true,
        timeout: 60000,
      },
});
