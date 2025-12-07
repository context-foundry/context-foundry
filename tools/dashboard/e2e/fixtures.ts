/**
 * Playwright Test Fixtures for Context Foundry Dashboard
 *
 * Provides API mocking and test data for E2E tests.
 */

import { test as base, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

// Sample job data for mocking
export const mockJobs = [
  {
    id: 'job-001-test',
    job_id: 'job-001-test',
    type: 'autonomous_build',
    status: 'running',
    priority: 5,
    created_at: new Date().toISOString(),
    started_at: new Date().toISOString(),
    completed_at: null,
    params: {
      task: 'Build a retro neon calculator with flip animation',
      working_directory: '/Users/test/projects/calculator',
    },
    metadata: {},
    result: null,
  },
  {
    id: 'job-002-test',
    job_id: 'job-002-test',
    type: 'autonomous_build',
    status: 'succeeded',
    priority: 5,
    created_at: new Date(Date.now() - 3600000).toISOString(),
    started_at: new Date(Date.now() - 3600000).toISOString(),
    completed_at: new Date(Date.now() - 1800000).toISOString(),
    params: {
      task: 'Create REST API with authentication',
      working_directory: '/Users/test/projects/api',
    },
    metadata: {},
    result: { success: true },
  },
  {
    id: 'job-003-test',
    job_id: 'job-003-test',
    type: 'autonomous_build',
    status: 'failed',
    priority: 3,
    created_at: new Date(Date.now() - 7200000).toISOString(),
    started_at: new Date(Date.now() - 7200000).toISOString(),
    completed_at: new Date(Date.now() - 6000000).toISOString(),
    params: {
      task: 'Fix database connection pooling',
      working_directory: '/Users/test/projects/db-fix',
    },
    metadata: {},
    result: { error: 'Connection timeout' },
  },
];

export const mockConversation = [
  {
    role: 'assistant',
    content: 'I\'ll help you build a retro neon calculator with flip animation. Let me start by analyzing the requirements...',
    timestamp: new Date().toISOString(),
  },
  {
    role: 'user',
    content: 'Make sure the buttons are big and have a glow effect',
    timestamp: new Date().toISOString(),
  },
  {
    role: 'assistant',
    content: 'Got it! I\'ll implement large buttons with CSS glow effects using box-shadow and text-shadow for that neon aesthetic.',
    timestamp: new Date().toISOString(),
  },
];

export const mockArtifacts = [
  {
    name: 'index.html',
    path: '/Users/test/projects/calculator/index.html',
    type: 'html',
    content: '<!DOCTYPE html><html>...</html>',
    size: 1024,
  },
  {
    name: 'styles.css',
    path: '/Users/test/projects/calculator/styles.css',
    type: 'css',
    content: '.calculator { background: #1a1a2e; }',
    size: 2048,
  },
];

/**
 * Setup API mocking for the dashboard
 */
export async function setupApiMocks(page: Page) {
  // Mock the daemon status endpoint
  await page.route('**/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'running',
        version: '0.1.0',
        uptime_seconds: 3600,
        jobs: {
          total: mockJobs.length,
          running: 1,
          queued: 0,
          succeeded: 1,
          failed: 1,
        },
      }),
    });
  });

  // Mock jobs list endpoint
  await page.route('**/api/jobs**', async (route) => {
    const url = new URL(route.request().url());
    const status = url.searchParams.get('status');

    let filteredJobs = mockJobs;
    if (status && status !== 'all') {
      filteredJobs = mockJobs.filter((j) => j.status === status);
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        jobs: filteredJobs,
        summary: {
          total: filteredJobs.length,
          running: filteredJobs.filter((j) => j.status === 'running').length,
          succeeded: filteredJobs.filter((j) => j.status === 'succeeded').length,
          failed: filteredJobs.filter((j) => j.status === 'failed').length,
        },
      }),
    });
  });

  // Mock single job endpoint
  await page.route('**/api/jobs/job-*', async (route) => {
    const url = route.request().url();
    const jobId = url.split('/').pop()?.split('?')[0];
    const job = mockJobs.find((j) => j.id === jobId);

    if (job) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(job),
      });
    } else {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Job not found' }),
      });
    }
  });

  // Mock conversation endpoint
  await page.route('**/api/jobs/*/conversation**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: 'job-001-test',
        phase: 'Scout',
        messages: mockConversation,
      }),
    });
  });

  // Mock artifacts endpoint
  await page.route('**/api/jobs/*/artifacts**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: 'job-001-test',
        phase: 'Scout',
        artifacts: mockArtifacts,
      }),
    });
  });

  // Mock sidekick chat endpoint
  await page.route('**/api/sidekick-chat', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        response: 'Hey there! I\'m your Sidekick assistant. How can I help you today?',
      }),
    });
  });

  // Mock pending approvals
  await page.route('**/api/pending-approvals', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  // Mock auth token endpoint
  await page.route('**/auth-token', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ token: 'test-token-12345' }),
    });
  });
}

// Extended test fixture with API mocking
export const test = base.extend<{ mockApi: void }>({
  mockApi: async ({ page }, use) => {
    await setupApiMocks(page);
    await use();
  },
});

export { expect };
