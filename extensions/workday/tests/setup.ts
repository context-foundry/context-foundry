/**
 * Vitest Setup File
 *
 * Configures the testing environment for all test files.
 */

import '@testing-library/jest-dom';
import { expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock environment variables
process.env.OPENAI_API_KEY = 'test-api-key';
process.env.KV_REST_API_URL = 'http://localhost:8080';
process.env.KV_REST_API_TOKEN = 'test-token';

// Mock IndexedDB
const indexedDB = {
  open: () => ({
    onsuccess: null,
    onerror: null,
    result: {
      transaction: () => ({
        objectStore: () => ({
          get: () => ({ onsuccess: null }),
          put: () => ({ onsuccess: null }),
          delete: () => ({ onsuccess: null }),
        }),
      }),
    },
  }),
};

global.indexedDB = indexedDB as any;

// Suppress console errors in tests (optional - remove if you want to see errors)
global.console = {
  ...console,
  error: () => {}, // Suppress error logs
  warn: () => {},  // Suppress warning logs
};
