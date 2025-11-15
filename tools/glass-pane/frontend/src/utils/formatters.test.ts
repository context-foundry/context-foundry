import { describe, it, expect } from 'vitest';
import { formatDuration, formatBytes } from './formatters';

describe('Formatters', () => {
  it('should format duration correctly', () => {
    expect(formatDuration(0)).toBe('0s');
    expect(formatDuration(45)).toBe('45s');
    expect(formatDuration(90)).toBe('1m 30s');
    expect(formatDuration(3661)).toBe('1h 1m 1s');
  });

  it('should format bytes correctly', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1024)).toBe('1 KB');
    expect(formatBytes(1048576)).toBe('1 MB');
    expect(formatBytes(1500)).toBe('1.46 KB');
  });
});
