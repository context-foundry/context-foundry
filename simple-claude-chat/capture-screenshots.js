import { chromium } from 'playwright';
import { writeFile, mkdir } from 'fs/promises';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const SCREENSHOT_DIR = join(__dirname, 'docs', 'screenshots');

/**
 * Screenshot capture script for Simple Claude Chat UI
 * Captures hero and feature screenshots for documentation
 */
async function captureScreenshots() {
  console.log('🎬 Starting screenshot capture...');
  console.log(`📍 Base URL: ${BASE_URL}`);
  console.log(`📁 Screenshot directory: ${SCREENSHOT_DIR}`);

  const manifest = {
    generated: new Date().toISOString(),
    baseURL: BASE_URL,
    projectType: 'web-app',
    screenshots: [],
    total: 0,
    failed: 0
  };

  let browser;

  try {
    // Launch browser
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1280, height: 720 }
    });
    const page = await context.newPage();

    // Navigate to application
    console.log('\n📡 Navigating to application...');
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 10000 });
    console.log('✅ Page loaded successfully');

    // Wait for main UI elements to be visible
    await page.waitForSelector('body', { timeout: 5000 });

    // Screenshot 1: Hero screenshot (initial/empty state)
    console.log('\n📸 Capturing hero screenshot...');
    const heroPath = join(SCREENSHOT_DIR, 'hero.png');
    await page.screenshot({ path: heroPath, fullPage: false });
    manifest.screenshots.push({
      filename: 'hero.png',
      path: 'docs/screenshots/hero.png',
      type: 'hero',
      description: 'Main chat interface - initial state'
    });
    console.log(`✅ Hero screenshot saved: ${heroPath}`);

    // Screenshot 2: Initial state (zoomed in on chat interface)
    console.log('\n📸 Capturing initial state...');
    const initialStatePath = join(SCREENSHOT_DIR, 'step-01-initial-state.png');
    await page.screenshot({ path: initialStatePath, fullPage: false });
    manifest.screenshots.push({
      filename: 'step-01-initial-state.png',
      path: 'docs/screenshots/step-01-initial-state.png',
      type: 'step',
      description: 'Initial application state - empty chat'
    });
    console.log(`✅ Initial state captured: ${initialStatePath}`);

    // Screenshot 3: Try to find and interact with input field
    console.log('\n📸 Capturing input field feature...');
    try {
      // Look for common input selectors in chat apps
      const inputSelectors = [
        'input[type="text"]',
        'textarea',
        'input[placeholder*="message" i]',
        'input[placeholder*="type" i]',
        '[role="textbox"]',
        '.message-input',
        '#message-input'
      ];

      let inputFound = false;
      for (const selector of inputSelectors) {
        try {
          const input = await page.$(selector);
          if (input) {
            await input.focus();
            const inputPath = join(SCREENSHOT_DIR, 'feature-01-input-field.png');
            await page.screenshot({ path: inputPath, fullPage: false });
            manifest.screenshots.push({
              filename: 'feature-01-input-field.png',
              path: 'docs/screenshots/feature-01-input-field.png',
              type: 'feature',
              description: 'Message input field focused'
            });
            console.log(`✅ Input field screenshot saved: ${inputPath}`);
            inputFound = true;
            break;
          }
        } catch (e) {
          // Continue to next selector
        }
      }

      if (!inputFound) {
        console.log('⚠️  Input field not found, skipping input feature screenshot');
      }
    } catch (error) {
      console.log(`⚠️  Could not capture input field: ${error.message}`);
    }

    // Screenshot 4: Full interface overview
    console.log('\n📸 Capturing full interface overview...');
    const overviewPath = join(SCREENSHOT_DIR, 'feature-02-interface-overview.png');
    await page.screenshot({ path: overviewPath, fullPage: true });
    manifest.screenshots.push({
      filename: 'feature-02-interface-overview.png',
      path: 'docs/screenshots/feature-02-interface-overview.png',
      type: 'feature',
      description: 'Complete chat interface layout'
    });
    console.log(`✅ Overview screenshot saved: ${overviewPath}`);

    // Update manifest totals
    manifest.total = manifest.screenshots.length;

    // Save manifest
    const manifestPath = join(SCREENSHOT_DIR, 'manifest.json');
    await writeFile(manifestPath, JSON.stringify(manifest, null, 2));
    console.log(`\n✅ Manifest saved: ${manifestPath}`);

    // Summary
    console.log('\n' + '='.repeat(50));
    console.log('📊 Screenshot Capture Summary:');
    console.log('='.repeat(50));
    console.log(`✅ Total screenshots: ${manifest.total}`);
    console.log(`❌ Failed: ${manifest.failed}`);
    console.log(`📁 Location: ${SCREENSHOT_DIR}`);
    console.log('='.repeat(50));

    manifest.screenshots.forEach((shot, idx) => {
      console.log(`${idx + 1}. ${shot.type.toUpperCase()}: ${shot.filename}`);
      console.log(`   ${shot.description}`);
    });

  } catch (error) {
    console.error('\n❌ Screenshot capture failed:', error.message);
    manifest.failed = manifest.screenshots.length;

    // Save partial manifest even on failure
    try {
      const manifestPath = join(SCREENSHOT_DIR, 'manifest.json');
      await writeFile(manifestPath, JSON.stringify(manifest, null, 2));
    } catch (e) {
      console.error('Failed to save manifest:', e.message);
    }

    process.exit(1);
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

// Run the script
captureScreenshots().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
