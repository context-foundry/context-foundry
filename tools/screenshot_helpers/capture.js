/**
 * Context Foundry - Automated Screenshot Capture
 *
 * This script uses Playwright to capture screenshots of built applications
 * for inclusion in automatically generated documentation.
 *
 * Usage: node capture.js [options]
 */

import { chromium } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Configuration from environment or defaults
 */
const config = {
  baseURL: process.env.BASE_URL || 'http://localhost:3000',
  outputDir: process.env.OUTPUT_DIR || 'docs/screenshots',
  timeout: parseInt(process.env.TIMEOUT || '30000'),
  viewport: {
    width: parseInt(process.env.VIEWPORT_WIDTH || '1280'),
    height: parseInt(process.env.VIEWPORT_HEIGHT || '720')
  },
  waitAfterLoad: parseInt(process.env.WAIT_AFTER_LOAD || '2000'),
  fullPage: process.env.FULL_PAGE !== 'false'
};

/**
 * Ensure output directory exists
 */
function ensureOutputDir() {
  if (!fs.existsSync(config.outputDir)) {
    fs.mkdirSync(config.outputDir, { recursive: true });
    console.log(`✓ Created output directory: ${config.outputDir}`);
  }
}

/**
 * Wait for page to be fully loaded and stable
 */
async function waitForPageReady(page) {
  try {
    // Wait for network to be idle
    await page.waitForLoadState('networkidle', { timeout: config.timeout });

    // Wait for DOM to be ready
    await page.waitForLoadState('domcontentloaded', { timeout: config.timeout });

    // Additional wait for any animations/hydration
    await page.waitForTimeout(config.waitAfterLoad);

    console.log('  ✓ Page is ready');
  } catch (error) {
    console.warn(`  ⚠ Warning: Page load wait had issues: ${error.message}`);
    // Continue anyway - page might still be usable
  }
}

/**
 * Capture a single screenshot
 */
async function captureScreenshot(page, filename, options = {}) {
  const filepath = path.join(config.outputDir, filename);

  try {
    await page.screenshot({
      path: filepath,
      fullPage: options.fullPage ?? config.fullPage,
      ...options
    });

    console.log(`  ✓ Captured: ${filename}`);
    return { success: true, filename, filepath };
  } catch (error) {
    console.error(`  ✗ Failed to capture ${filename}: ${error.message}`);
    return { success: false, filename, error: error.message };
  }
}

/**
 * Detect project type from package.json and files
 */
function detectProjectType() {
  // Check for package.json
  if (fs.existsSync('package.json')) {
    const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
    const deps = { ...pkg.dependencies, ...pkg.devDependencies };

    // Check for common frameworks
    if (deps['react'] || deps['next'] || deps['react-dom']) return 'react-app';
    if (deps['vue'] || deps['nuxt']) return 'vue-app';
    if (deps['@angular/core']) return 'angular-app';
    if (deps['svelte']) return 'svelte-app';
    if (deps['phaser'] || deps['pixijs']) return 'game';
    if (deps['express'] || deps['fastify'] || deps['koa']) return 'api';

    // Check for canvas/game keywords
    if (pkg.keywords && pkg.keywords.some(k => ['game', 'canvas'].includes(k))) {
      return 'game';
    }
  }

  // Check for HTML with canvas
  if (fs.existsSync('index.html')) {
    const html = fs.readFileSync('index.html', 'utf8');
    if (html.includes('<canvas')) return 'game';
  }

  return 'web-app'; // Default fallback
}

/**
 * Capture screenshots for a web app/game
 */
async function captureWebApp() {
  const results = [];
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  try {
    const context = await browser.newContext({
      viewport: config.viewport,
      deviceScaleFactor: 2 // Retina/high-DPI screenshots
    });

    const page = await context.newPage();

    // Set longer timeout for navigation
    page.setDefaultTimeout(config.timeout);

    console.log(`\n📸 Navigating to ${config.baseURL}...`);

    try {
      await page.goto(config.baseURL, {
        waitUntil: 'domcontentloaded',
        timeout: config.timeout
      });
    } catch (error) {
      throw new Error(`Failed to navigate to ${config.baseURL}: ${error.message}. Is the dev server running?`);
    }

    // Wait for page to be ready
    await waitForPageReady(page);

    // 1. Hero screenshot (homepage/main view)
    console.log('\n📸 Capturing hero screenshot...');
    results.push(await captureScreenshot(page, 'hero.png', { fullPage: true }));

    // 2. Feature screenshots
    const projectType = detectProjectType();
    console.log(`\n📸 Detected project type: ${projectType}`);
    console.log('📸 Capturing feature screenshots...');

    if (projectType === 'game') {
      // For games, capture after some gameplay time
      console.log('  Waiting for game initialization...');
      await page.waitForTimeout(3000);
      results.push(await captureScreenshot(page, 'feature-01-gameplay.png'));

      // Try to interact with game (click to start, etc.)
      try {
        await page.click('canvas');
        await page.waitForTimeout(2000);
        results.push(await captureScreenshot(page, 'feature-02-gameplay-active.png'));
      } catch (e) {
        console.log('  ⚠ Could not interact with game canvas (expected for some games)');
      }
    } else {
      // For web apps, try to capture different states

      // Try clicking first interactive element
      try {
        const buttons = await page.$$('button');
        if (buttons.length > 0) {
          console.log('  Capturing interaction screenshot...');
          await buttons[0].click();
          await page.waitForTimeout(1000);
          results.push(await captureScreenshot(page, 'feature-01-interaction.png'));
        }
      } catch (e) {
        console.log('  ⚠ No interactive elements found or interaction failed');
      }

      // Try to capture a form if present
      try {
        const inputs = await page.$$('input[type="text"], textarea');
        if (inputs.length > 0) {
          console.log('  Capturing form screenshot...');
          await inputs[0].fill('Example input');
          await page.waitForTimeout(500);
          results.push(await captureScreenshot(page, 'feature-02-form.png'));
        }
      } catch (e) {
        console.log('  ⚠ No form elements found or interaction failed');
      }
    }

    // 3. Step-by-step screenshots (try to capture workflow)
    console.log('\n📸 Capturing workflow screenshots...');

    // Reset to homepage
    await page.goto(config.baseURL);
    await waitForPageReady(page);
    results.push(await captureScreenshot(page, 'step-01-initial-state.png'));

    // Try to capture a complete user flow
    try {
      const allButtons = await page.$$('button, a[href]:not([href="#"])');

      for (let i = 0; i < Math.min(3, allButtons.length); i++) {
        await allButtons[i].click();
        await page.waitForTimeout(1000);
        results.push(await captureScreenshot(page, `step-${String(i + 2).padStart(2, '0')}-action-${i + 1}.png`));
      }
    } catch (e) {
      console.log('  ⚠ Could not capture full workflow (expected for simple apps)');
    }

  } finally {
    await browser.close();
  }

  return results;
}

/**
 * Create manifest.json documenting all screenshots
 */
function createManifest(results) {
  const manifest = {
    generated: new Date().toISOString(),
    baseURL: config.baseURL,
    projectType: detectProjectType(),
    screenshots: results.filter(r => r.success).map(r => ({
      filename: r.filename,
      path: r.filepath,
      type: r.filename.startsWith('hero') ? 'hero' :
            r.filename.startsWith('feature') ? 'feature' :
            r.filename.startsWith('step') ? 'step' : 'other'
    })),
    total: results.filter(r => r.success).length,
    failed: results.filter(r => !r.success).length
  };

  const manifestPath = path.join(config.outputDir, 'manifest.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.log(`\n✓ Created manifest: ${manifestPath}`);

  return manifest;
}

/**
 * Main execution
 */
async function main() {
  console.log('🚀 Context Foundry - Screenshot Capture');
  console.log('=====================================\n');
  console.log(`Base URL: ${config.baseURL}`);
  console.log(`Output Directory: ${config.outputDir}`);
  console.log(`Viewport: ${config.viewport.width}x${config.viewport.height}`);
  console.log(`Full Page: ${config.fullPage}`);

  ensureOutputDir();

  try {
    const results = await captureWebApp();
    const manifest = createManifest(results);

    console.log('\n📊 Summary:');
    console.log(`  ✓ ${manifest.total} screenshots captured successfully`);
    if (manifest.failed > 0) {
      console.log(`  ✗ ${manifest.failed} screenshots failed`);
    }
    console.log(`  📁 Saved to: ${config.outputDir}`);

    // Exit with error if no screenshots captured
    if (manifest.total === 0) {
      console.error('\n❌ No screenshots were captured!');
      process.exit(1);
    }

    console.log('\n✅ Screenshot capture complete!');
    process.exit(0);

  } catch (error) {
    console.error('\n❌ Screenshot capture failed:');
    console.error(error.message);
    console.error('\nTips:');
    console.error('  - Ensure the dev server is running at the BASE_URL');
    console.error('  - Check that Playwright browsers are installed: npx playwright install');
    console.error('  - Verify the application loads correctly in a browser');
    process.exit(1);
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { captureWebApp, captureScreenshot, ensureOutputDir, detectProjectType };
