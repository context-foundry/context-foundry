/**
 * Tests for document processing functionality (TypeScript)
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { analyzeDocument } from '../src/examples/documentProcessing.js';
import { existsSync, writeFileSync, mkdirSync } from 'fs';
import { resolve } from 'path';

describe('Document Processing', () => {
  const testFile = resolve(__dirname, '../../test_data/sample.pdf');

  beforeAll(() => {
    // Ensure test file exists
    if (!existsSync(testFile)) {
      mkdirSync(resolve(__dirname, '../../test_data'), { recursive: true });
      writeFileSync(testFile, 'Test document content');
    }
  });

  it('should return correct structure', async () => {
    const questions = ['What is the main topic?'];
    const result = await analyzeDocument(testFile, questions);

    // Verify structure
    expect(result).toHaveProperty('summary');
    expect(result).toHaveProperty('key_findings');
    expect(result).toHaveProperty('answers');
    expect(result).toHaveProperty('confidence_score');

    // Verify types
    expect(typeof result.summary).toBe('string');
    expect(Array.isArray(result.key_findings)).toBe(true);
    expect(typeof result.answers).toBe('object');
    expect(typeof result.confidence_score).toBe('number');

    // Verify confidence score range
    expect(result.confidence_score).toBeGreaterThanOrEqual(0);
    expect(result.confidence_score).toBeLessThanOrEqual(1);
  });

  it('should handle missing file', async () => {
    await expect(
      analyzeDocument('/nonexistent/file.pdf', ['question'])
    ).rejects.toThrow();
  });
});
