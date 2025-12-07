/**
 * Sidekick Chat E2E Tests
 *
 * Tests for the AI assistant chat functionality including:
 * - Opening/closing the chat modal
 * - Sending messages
 * - Receiving responses
 * - Build request triggering
 */

import { test, expect } from './fixtures';

test.describe('Sidekick Chat', () => {
  test.beforeEach(async ({ page, mockApi }) => {
    await page.goto('/');
  });

  test('should have sidekick input visible', async ({ page }) => {
    // Look for the sidekick input
    const sidekickInput = page.locator(
      '.sidekick-input, [class*="sidekick"] input, input[placeholder*="command"], input[placeholder*="chat"]'
    );
    await expect(sidekickInput.first()).toBeVisible({ timeout: 10000 });
  });

  test('should open chat modal when typing and pressing Enter', async ({ page }) => {
    // Find and interact with sidekick input
    const sidekickInput = page.locator(
      '.sidekick-input, [class*="sidekick"] input, input[placeholder*="command"]'
    ).first();

    await sidekickInput.fill('Hello');
    await sidekickInput.press('Enter');

    // Modal should open
    const modal = page.locator('.sidekick-modal, [class*="sidekick-modal"]');
    await expect(modal).toBeVisible({ timeout: 5000 });
  });

  test('should display user message in chat', async ({ page }) => {
    const sidekickInput = page.locator(
      '.sidekick-input, [class*="sidekick"] input, input[placeholder*="command"]'
    ).first();

    const testMessage = 'Build me a calculator app';
    await sidekickInput.fill(testMessage);
    await sidekickInput.press('Enter');

    // Wait for modal and check message
    await page.waitForSelector('.sidekick-modal, [class*="sidekick-modal"]');

    const userMessage = page.locator('.sidekick-message.user, [class*="message"][class*="user"]');
    await expect(userMessage).toContainText(testMessage);
  });

  test('should receive assistant response', async ({ page }) => {
    const sidekickInput = page.locator(
      '.sidekick-input, [class*="sidekick"] input, input[placeholder*="command"]'
    ).first();

    await sidekickInput.fill('Hello');
    await sidekickInput.press('Enter');

    // Wait for API response
    await page.waitForResponse('**/api/sidekick-chat');

    // Should show assistant message
    const assistantMessage = page.locator(
      '.sidekick-message.assistant, [class*="message"][class*="assistant"]'
    );
    await expect(assistantMessage.first()).toBeVisible({ timeout: 10000 });
  });

  test('should close modal when clicking close button', async ({ page }) => {
    const sidekickInput = page.locator(
      '.sidekick-input, [class*="sidekick"] input, input[placeholder*="command"]'
    ).first();

    await sidekickInput.fill('Test');
    await sidekickInput.press('Enter');

    // Wait for modal
    const modal = page.locator('.sidekick-modal, [class*="sidekick-modal"]');
    await expect(modal).toBeVisible();

    // Click close button
    const closeBtn = page.locator('.sidekick-modal-close, [class*="close"]').first();
    await closeBtn.click();

    // Modal should be hidden
    await expect(modal).not.toBeVisible();
  });

  test('should close modal when clicking overlay', async ({ page }) => {
    const sidekickInput = page.locator(
      '.sidekick-input, [class*="sidekick"] input, input[placeholder*="command"]'
    ).first();

    await sidekickInput.fill('Test');
    await sidekickInput.press('Enter');

    const modal = page.locator('.sidekick-modal, [class*="sidekick-modal"]');
    await expect(modal).toBeVisible();

    // Click overlay (outside modal)
    const overlay = page.locator('.sidekick-modal-overlay, [class*="overlay"]');
    await overlay.click({ position: { x: 10, y: 10 } });

    await expect(modal).not.toBeVisible();
  });

  test('should have copy button on messages', async ({ page }) => {
    const sidekickInput = page.locator(
      '.sidekick-input, [class*="sidekick"] input, input[placeholder*="command"]'
    ).first();

    await sidekickInput.fill('Hello');
    await sidekickInput.press('Enter');

    await page.waitForResponse('**/api/sidekick-chat');

    // Should have copy buttons
    const copyBtn = page.locator('.sidekick-copy-btn, button:has-text("Copy")');
    await expect(copyBtn.first()).toBeVisible({ timeout: 10000 });
  });

  test('should show loading state while waiting for response', async ({ page }) => {
    // Delay the API response
    await page.route('**/api/sidekick-chat', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ response: 'Delayed response' }),
      });
    });

    const sidekickInput = page.locator(
      '.sidekick-input, [class*="sidekick"] input, input[placeholder*="command"]'
    ).first();

    await sidekickInput.fill('Hello');
    await sidekickInput.press('Enter');

    // Should show loading indicator
    const loading = page.locator('.thinking, [class*="loading"], [class*="spinner"]');
    await expect(loading.first()).toBeVisible({ timeout: 5000 });
  });
});
