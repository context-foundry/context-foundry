import { defineConfig } from '@playwright/test';

/**
 * Playwright configuration for screenshot capture
 * Used by screenshot capture script to document the application
 */
export default defineConfig({
  testDir: './screenshots',
  timeout: 30000,
  fullyParallel: false,
  forbidOnly: false,
  retries: 0,
  workers: 1,
  reporter: 'list',

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:5173',
    trace: 'off',
    screenshot: 'only-on-failure',
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
  },

  webServer: undefined, // Server started manually
});
