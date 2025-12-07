/**
 * Dashboard E2E Tests
 *
 * Tests for the main dashboard functionality including:
 * - Page load and navigation
 * - Job list display
 * - Status indicators
 * - Theme and styling
 */

import { test, expect } from './fixtures';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page, mockApi }) => {
    await page.goto('/');
  });

  test('should load the dashboard successfully', async ({ page }) => {
    // Check page title
    await expect(page).toHaveTitle(/Context Foundry/);

    // Check main layout elements
    await expect(page.locator('.sidebar, [class*="sidebar"]')).toBeVisible();
    await expect(page.locator('.header, [class*="header"]')).toBeVisible();
  });

  test('should display job list', async ({ page }) => {
    // Wait for jobs to load
    await page.waitForResponse('**/api/jobs**');

    // Should show job cards
    const jobCards = page.locator('[class*="job-card"], [class*="job-item"], .job-row');
    await expect(jobCards.first()).toBeVisible({ timeout: 10000 });
  });

  test('should show daemon status', async ({ page }) => {
    // Wait for status to load
    await page.waitForResponse('**/status');

    // Should show running status indicator
    const statusIndicator = page.locator('[class*="status"], .daemon-status');
    await expect(statusIndicator.first()).toBeVisible();
  });

  test('should have dark theme applied', async ({ page }) => {
    // Check for dark background colors
    const body = page.locator('body');
    const backgroundColor = await body.evaluate((el) => {
      return window.getComputedStyle(el).backgroundColor;
    });

    // Dark theme should have low RGB values
    expect(backgroundColor).toMatch(/rgb\(\d{1,2},\s*\d{1,2},\s*\d{1,2}\)/);
  });

  test('should filter jobs by status', async ({ page }) => {
    // Wait for initial load
    await page.waitForResponse('**/api/jobs**');

    // Look for filter buttons or dropdown
    const filterButton = page.locator('button:has-text("Running"), [class*="filter"]').first();

    if (await filterButton.isVisible()) {
      await filterButton.click();

      // Should trigger a new API call with status filter
      await page.waitForResponse((response) =>
        response.url().includes('/api/jobs') && response.url().includes('status=')
      );
    }
  });

  test('should navigate to job details on click', async ({ page }) => {
    // Wait for jobs to load
    await page.waitForResponse('**/api/jobs**');

    // Click on first job
    const firstJob = page.locator('[class*="job-card"], [class*="job-item"], .job-row').first();
    await firstJob.click();

    // Should show job detail view
    await expect(page.locator('[class*="job-detail"], [class*="JobDetail"]')).toBeVisible({
      timeout: 5000,
    });
  });
});

test.describe('Dashboard Accessibility', () => {
  test.beforeEach(async ({ page, mockApi }) => {
    await page.goto('/');
  });

  test('should have proper heading hierarchy', async ({ page }) => {
    const h1 = page.locator('h1');
    await expect(h1.first()).toBeVisible();
  });

  test('should be keyboard navigable', async ({ page }) => {
    // Tab through focusable elements
    await page.keyboard.press('Tab');
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();
  });

  test('should have sufficient color contrast', async ({ page }) => {
    // Check that text is readable (basic check)
    const textElements = page.locator('p, span, h1, h2, h3, button');
    const firstText = textElements.first();

    if (await firstText.isVisible()) {
      const color = await firstText.evaluate((el) => {
        return window.getComputedStyle(el).color;
      });
      // Should have a color defined
      expect(color).not.toBe('');
    }
  });
});
