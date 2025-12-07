/**
 * Screenshot Tests for Documentation
 *
 * Captures hero screenshots for README and documentation.
 * Run with: npx playwright test e2e/screenshot.spec.ts
 */

import { test, expect } from './fixtures';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SCREENSHOT_DIR = path.join(__dirname, '..', '..', '..', 'docs', 'images');

test.describe('Documentation Screenshots', () => {
  test.beforeEach(async ({ page, mockApi }) => {
    // Set viewport for consistent screenshots
    await page.setViewportSize({ width: 1400, height: 900 });
  });

  test('capture hero screenshot - dashboard overview', async ({ page }) => {
    await page.goto('/');
    await page.waitForResponse('**/api/jobs**');

    // Wait for animations to settle
    await page.waitForTimeout(1000);

    // Capture full dashboard
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'dashboard-hero.png'),
      fullPage: false,
    });
  });

  test('capture job detail screenshot', async ({ page }) => {
    await page.goto('/');
    await page.waitForResponse('**/api/jobs**');

    // Click on first job
    const firstJob = page.locator('[class*="job-card"], [class*="job-item"], .job-row').first();
    await firstJob.click();

    await page.waitForSelector('[class*="job-detail"], [class*="JobDetail"]', { timeout: 5000 });
    await page.waitForTimeout(500);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'job-detail.png'),
      fullPage: false,
    });
  });

  test('capture sidekick chat screenshot', async ({ page }) => {
    await page.goto('/');

    // Open sidekick
    const sidekickInput = page.locator(
      '.sidekick-input, [class*="sidekick"] input, input[placeholder*="command"]'
    ).first();

    await sidekickInput.fill('Build me a retro calculator app');
    await sidekickInput.press('Enter');

    // Wait for modal and response
    await page.waitForSelector('.sidekick-modal, [class*="sidekick-modal"]');
    await page.waitForResponse('**/api/sidekick-chat').catch(() => {});
    await page.waitForTimeout(500);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'sidekick-chat.png'),
      fullPage: false,
    });
  });

  test('capture dark theme showcase', async ({ page }) => {
    await page.goto('/');
    await page.waitForResponse('**/api/jobs**');

    // Get multiple UI states for a montage-style shot
    await page.waitForTimeout(1000);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'dark-theme-showcase.png'),
      fullPage: true,
    });
  });
});

test.describe('Feature Screenshots', () => {
  test.beforeEach(async ({ page, mockApi }) => {
    await page.setViewportSize({ width: 1200, height: 800 });
  });

  test('capture collapsible sections', async ({ page }) => {
    await page.goto('/');
    await page.waitForResponse('**/api/jobs**');

    const firstJob = page.locator('[class*="job-card"], [class*="job-item"], .job-row').first();
    await firstJob.click();
    await page.waitForSelector('[class*="job-detail"]', { timeout: 5000 });

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'collapsible-sections.png'),
      fullPage: false,
    });
  });

  test('capture search functionality', async ({ page }) => {
    await page.goto('/');
    await page.waitForResponse('**/api/jobs**');

    const firstJob = page.locator('[class*="job-card"], [class*="job-item"], .job-row').first();
    await firstJob.click();
    await page.waitForSelector('[class*="job-detail"]', { timeout: 5000 });

    // Try to use search if available
    const searchBox = page.locator('.search-box input, input[placeholder*="Search"]').first();
    if (await searchBox.isVisible()) {
      await searchBox.fill('function');
      await page.waitForTimeout(300);
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'search-feature.png'),
      fullPage: false,
    });
  });

  test('capture mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 }); // iPhone 14 Pro
    await page.goto('/');
    await page.waitForResponse('**/api/jobs**');
    await page.waitForTimeout(500);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'mobile-view.png'),
      fullPage: false,
    });
  });
});
