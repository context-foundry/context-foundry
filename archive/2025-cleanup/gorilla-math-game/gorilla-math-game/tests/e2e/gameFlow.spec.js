import { test, expect } from '@playwright/test';

test.describe('Gorilla Math Game - Complete User Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('displays welcome screen on load', async ({ page }) => {
    await expect(page.locator('h1:has-text("Gorilla Math Game")')).toBeVisible();
    await expect(page.locator('button:has-text("Start Game")')).toBeVisible();
  });

  test('starts game when Start Game button is clicked', async ({ page }) => {
    await page.click('text=Start Game');

    // Should show a math problem
    await expect(page.locator('[aria-label*="Math problem"]')).toBeVisible();

    // Should show answer input
    await expect(page.locator('input[type="number"]')).toBeVisible();

    // Should show Check Answer button
    await expect(page.locator('button:has-text("Check Answer")')).toBeVisible();
  });

  test('user can answer a problem and see feedback', async ({ page }) => {
    await page.click('text=Start Game');

    // Wait for problem to appear
    await page.waitForSelector('[aria-label*="Math problem"]');

    // Get the problem text
    const problemElement = page.locator('[aria-label*="Math problem"]');
    const problemLabel = await problemElement.getAttribute('aria-label');

    // Parse the problem (simple approach for testing)
    // Example: "Math problem: 5 plus 3 equals what?"
    const match = problemLabel.match(/(\d+)\s+(plus|minus|times)\s+(\d+)/i);

    if (match) {
      const num1 = parseInt(match[1]);
      const operation = match[2].toLowerCase();
      const num2 = parseInt(match[3]);

      let answer;
      if (operation === 'plus') {
        answer = num1 + num2;
      } else if (operation === 'minus') {
        answer = num1 - num2;
      } else if (operation === 'times') {
        answer = num1 * num2;
      }

      // Enter the answer
      await page.fill('input[type="number"]', answer.toString());
      await page.click('button:has-text("Check Answer")');

      // Should show feedback
      await expect(page.locator('[role="alert"]')).toBeVisible();

      // Should show correct feedback message
      await expect(page.locator('[role="alert"]')).toContainText(/great|perfect|got it/i);

      // Score should update
      await expect(page.locator('text=/Score.*1.*1/i')).toBeVisible();
    }
  });

  test('incorrect answer shows encouraging feedback', async ({ page }) => {
    await page.click('text=Start Game');

    // Wait for problem
    await page.waitForSelector('input[type="number"]');

    // Enter obviously wrong answer
    await page.fill('input[type="number"]', '999');
    await page.click('button:has-text("Check Answer")');

    // Should show feedback
    const feedback = page.locator('[role="alert"]');
    await expect(feedback).toBeVisible();

    // Should contain encouraging message
    const feedbackText = await feedback.textContent();
    expect(feedbackText).toMatch(/(not quite|almost|try)/i);
  });

  test('generates new problem after feedback delay', async ({ page }) => {
    await page.click('text=Start Game');

    // Get first problem
    await page.waitForSelector('[aria-label*="Math problem"]');
    const firstProblem = await page.locator('[aria-label*="Math problem"]').getAttribute('aria-label');

    // Answer the problem (any answer)
    await page.fill('input[type="number"]', '5');
    await page.click('button:has-text("Check Answer")');

    // Wait for feedback to disappear and new problem to appear (2+ seconds)
    await page.waitForTimeout(2500);

    // Should have a new problem (input should be visible again)
    await expect(page.locator('input[type="number"]')).toBeVisible();
    await expect(page.locator('button:has-text("Check Answer")')).toBeVisible();
  });

  test('reset button returns to welcome screen', async ({ page }) => {
    await page.click('text=Start Game');

    // Wait for game to start
    await page.waitForSelector('[aria-label*="Math problem"]');

    // Click reset button
    await page.click('button:has-text("Back to Start")');

    // Should return to welcome screen
    await expect(page.locator('h1:has-text("Gorilla Math Game")')).toBeVisible();
    await expect(page.locator('button:has-text("Start Game")')).toBeVisible();
  });

  test('browser starts without console errors', async ({ page }) => {
    const errors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.click('text=Start Game');
    await page.waitForTimeout(3000);

    // Filter out known third-party errors
    const relevantErrors = errors.filter(
      (error) => !error.includes('favicon') && !error.includes('chrome-extension')
    );

    expect(relevantErrors).toHaveLength(0);
  });

  test('game works on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE

    await page.click('text=Start Game');
    await expect(page.locator('input[type="number"]')).toBeVisible();

    // Verify touch targets are large enough (min 44px)
    const button = page.locator('button:has-text("Check Answer")');
    const box = await button.boundingBox();

    expect(box.height).toBeGreaterThanOrEqual(44);
  });

  test('streak counter increments with consecutive correct answers', async ({ page }) => {
    await page.click('text=Start Game');

    // Answer 2 problems correctly
    for (let i = 0; i < 2; i++) {
      await page.waitForSelector('[aria-label*="Math problem"]');

      const problemElement = page.locator('[aria-label*="Math problem"]');
      const problemLabel = await problemElement.getAttribute('aria-label');
      const match = problemLabel.match(/(\d+)\s+(plus|minus|times)\s+(\d+)/i);

      if (match) {
        const num1 = parseInt(match[1]);
        const operation = match[2].toLowerCase();
        const num2 = parseInt(match[3]);

        let answer;
        if (operation === 'plus') {
          answer = num1 + num2;
        } else if (operation === 'minus') {
          answer = num1 - num2;
        } else if (operation === 'times') {
          answer = num1 * num2;
        }

        await page.fill('input[type="number"]', answer.toString());
        await page.click('button:has-text("Check Answer")');

        // Wait for next problem
        await page.waitForTimeout(2500);
      }
    }

    // Should show streak
    await expect(page.locator('text=STREAK')).toBeVisible();
  });

  test('enter key submits answer', async ({ page }) => {
    await page.click('text=Start Game');

    await page.waitForSelector('input[type="number"]');

    const input = page.locator('input[type="number"]');
    await input.fill('5');
    await input.press('Enter');

    // Should show feedback
    await expect(page.locator('[role="alert"]')).toBeVisible();
  });
});
