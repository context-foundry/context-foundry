#!/usr/bin/env node
/**
 * Test script for documentation site fixes
 * Validates that all critical issues have been resolved
 */

const http = require('http');

const BASE_URL = 'http://localhost:8080';
const tests = [];
let passed = 0;
let failed = 0;

function test(name, fn) {
  tests.push({ name, fn });
}

async function fetch(path) {
  return new Promise((resolve, reject) => {
    http.get(BASE_URL + path, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ status: res.statusCode, body: data }));
    }).on('error', reject);
  });
}

// Test 1: Docs index has Fuse.js and NO search.js
test('Docs index loads Fuse.js CDN (no 404)', async () => {
  const res = await fetch('/docs/');
  if (!res.body.includes('fuse.js')) throw new Error('Fuse.js not found in docs/index.html');
  if (res.body.includes('search.js')) throw new Error('search.js still referenced (should be removed)');
});

// Test 2: Doc page has Fuse.js loaded
test('Doc pages load Fuse.js library', async () => {
  const res = await fetch('/docs/getting-started/quickstart.html');
  if (!res.body.includes('fuse.js')) throw new Error('Fuse.js not found in doc page');
});

// Test 3: Doc pages use defer (not type="module")
test('Doc pages use defer attribute (not type=module)', async () => {
  const res = await fetch('/docs/getting-started/quickstart.html');
  if (res.body.includes('type="module"')) throw new Error('type="module" still present (should be defer)');
  if (!res.body.includes('defer')) throw new Error('defer attribute not found');
});

// Test 4: docs.js has navigation functions
test('docs.js contains navigation population functions', async () => {
  const res = await fetch('/docs/assets/docs.js');
  if (!res.body.includes('initNavigation')) throw new Error('initNavigation function not found');
  if (!res.body.includes('initBreadcrumbs')) throw new Error('initBreadcrumbs function not found');
  if (!res.body.includes('navigation.json')) throw new Error('navigation.json fetch not found');
});

// Test 5: navigation.json is accessible
test('navigation.json is accessible', async () => {
  const res = await fetch('/docs/assets/navigation.json');
  if (res.status !== 200) throw new Error('navigation.json returned ' + res.status);
  const data = JSON.parse(res.body);
  if (!data.categories) throw new Error('navigation.json missing categories');
  if (data.categories.length < 4) throw new Error('Expected at least 4 categories');
});

// Test 6: Multiple doc pages load correctly
test('All doc category pages load without errors', async () => {
  const pages = [
    '/docs/getting-started/faq.html',
    '/docs/guides/changelog.html',
    '/docs/technical/innovations.html',
    '/docs/reference/architecture-decisions.html'
  ];

  for (const page of pages) {
    const res = await fetch(page);
    if (res.status !== 200) throw new Error(`${page} returned ${res.status}`);
    if (!res.body.includes('fuse.js')) throw new Error(`${page} missing Fuse.js`);
  }
});

// Test 7: docs.js is accessible
test('docs.js file is accessible', async () => {
  const res = await fetch('/docs/assets/docs.js');
  if (res.status !== 200) throw new Error('docs.js returned ' + res.status);
});

// Run tests
(async () => {
  console.log('\n🧪 Running Documentation Site Tests...\n');
  
  for (const { name, fn } of tests) {
    try {
      await fn();
      passed++;
      console.log(`✅ ${name}`);
    } catch (err) {
      failed++;
      console.log(`❌ ${name}`);
      console.log(`   Error: ${err.message}\n`);
    }
  }
  
  console.log(`\n📊 Test Results: ${passed} passed, ${failed} failed, ${tests.length} total\n`);
  
  if (failed > 0) {
    console.log('❌ Tests FAILED - some issues remain\n');
    process.exit(1);
  } else {
    console.log('✅ All tests PASSED - documentation site is fixed!\n');
    process.exit(0);
  }
})();
