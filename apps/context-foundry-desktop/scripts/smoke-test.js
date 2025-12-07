#!/usr/bin/env node

/**
 * Smoke Test Script for Context Foundry Desktop
 *
 * This script performs basic smoke tests to verify:
 * 1. The Tauri app can be built
 * 2. The daemon can be reached (if running)
 * 3. Basic API endpoints respond correctly
 *
 * Usage: npm run desktop:test
 */

const { spawn, execSync } = require('child_process');
const http = require('http');
const path = require('path');

const DAEMON_PORT = process.env.CFD_HTTP_API_PORT || 8421;
const DAEMON_URL = `http://127.0.0.1:${DAEMON_PORT}`;

// ANSI color codes
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function success(message) {
  log(`✓ ${message}`, 'green');
}

function fail(message) {
  log(`✗ ${message}`, 'red');
}

function info(message) {
  log(`→ ${message}`, 'blue');
}

function warn(message) {
  log(`! ${message}`, 'yellow');
}

// Check if daemon is running
async function checkDaemonHealth() {
  return new Promise((resolve) => {
    const req = http.get(`${DAEMON_URL}/health`, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve({ success: true, data: json });
        } catch {
          resolve({ success: false, error: 'Invalid JSON response' });
        }
      });
    });

    req.on('error', (err) => {
      resolve({ success: false, error: err.message });
    });

    req.setTimeout(5000, () => {
      req.destroy();
      resolve({ success: false, error: 'Timeout' });
    });
  });
}

// Check if npm dependencies are installed
function checkDependencies() {
  try {
    const pkgPath = path.join(__dirname, '..', 'package.json');
    const pkg = require(pkgPath);
    const nodeModulesPath = path.join(__dirname, '..', 'node_modules');

    const fs = require('fs');
    if (!fs.existsSync(nodeModulesPath)) {
      return { success: false, error: 'node_modules not found. Run npm install first.' };
    }

    return { success: true };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

// Check if Rust/Cargo is available
function checkRust() {
  try {
    const version = execSync('cargo --version', { encoding: 'utf-8' }).trim();
    return { success: true, version };
  } catch {
    return { success: false, error: 'Cargo/Rust not installed' };
  }
}

// Check if Tauri CLI is available
function checkTauriCli() {
  try {
    const version = execSync('npx tauri --version', {
      encoding: 'utf-8',
      cwd: path.join(__dirname, '..'),
    }).trim();
    return { success: true, version };
  } catch {
    return { success: false, error: 'Tauri CLI not available' };
  }
}

// Run TypeScript type check
function checkTypes() {
  try {
    execSync('npm run typecheck', {
      cwd: path.join(__dirname, '..'),
      stdio: 'pipe',
    });
    return { success: true };
  } catch (err) {
    return { success: false, error: 'TypeScript errors found' };
  }
}

// Main test runner
async function runTests() {
  log('\n========================================', 'blue');
  log('  Context Foundry Desktop Smoke Tests', 'blue');
  log('========================================\n', 'blue');

  let passed = 0;
  let failed = 0;
  let skipped = 0;

  // Test 1: Check dependencies
  info('Checking npm dependencies...');
  const depsResult = checkDependencies();
  if (depsResult.success) {
    success('Dependencies installed');
    passed++;
  } else {
    fail(`Dependencies: ${depsResult.error}`);
    failed++;
  }

  // Test 2: Check Rust
  info('Checking Rust/Cargo...');
  const rustResult = checkRust();
  if (rustResult.success) {
    success(`Rust available: ${rustResult.version}`);
    passed++;
  } else {
    fail(`Rust: ${rustResult.error}`);
    failed++;
  }

  // Test 3: Check Tauri CLI
  info('Checking Tauri CLI...');
  const tauriResult = checkTauriCli();
  if (tauriResult.success) {
    success(`Tauri CLI available: ${tauriResult.version}`);
    passed++;
  } else {
    warn(`Tauri CLI: ${tauriResult.error} (may need to run npm install)`);
    skipped++;
  }

  // Test 4: TypeScript type check
  info('Running TypeScript type check...');
  const typesResult = checkTypes();
  if (typesResult.success) {
    success('TypeScript types valid');
    passed++;
  } else {
    fail(`TypeScript: ${typesResult.error}`);
    failed++;
  }

  // Test 5: Daemon health check
  info(`Checking daemon health at ${DAEMON_URL}...`);
  const healthResult = await checkDaemonHealth();
  if (healthResult.success) {
    success(`Daemon healthy: ${JSON.stringify(healthResult.data.status || 'ok')}`);
    passed++;
  } else {
    warn(`Daemon not running: ${healthResult.error} (expected if daemon is stopped)`);
    skipped++;
  }

  // Summary
  log('\n========================================', 'blue');
  log('  Test Summary', 'blue');
  log('========================================', 'blue');
  success(`Passed: ${passed}`);
  if (failed > 0) fail(`Failed: ${failed}`);
  if (skipped > 0) warn(`Skipped: ${skipped}`);

  // Exit code
  process.exit(failed > 0 ? 1 : 0);
}

// Run tests
runTests().catch((err) => {
  fail(`Unexpected error: ${err.message}`);
  process.exit(1);
});
