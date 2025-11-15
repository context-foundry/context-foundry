import { describe, it, expect } from 'vitest';
import { calculateTokenZone } from './tokenBudget';

describe('Token Budget Utils', () => {
  it('should return green zone for <40% usage', () => {
    expect(calculateTokenZone(30000, 200000)).toBe('green');
    expect(calculateTokenZone(79999, 200000)).toBe('green');
  });

  it('should return yellow zone for 40-70% usage', () => {
    expect(calculateTokenZone(80000, 200000)).toBe('yellow');
    expect(calculateTokenZone(139999, 200000)).toBe('yellow');
  });

  it('should return red zone for >70% usage', () => {
    expect(calculateTokenZone(140000, 200000)).toBe('red');
    expect(calculateTokenZone(200000, 200000)).toBe('red');
  });

  it('should handle edge cases', () => {
    expect(calculateTokenZone(0, 200000)).toBe('green');
    expect(calculateTokenZone(200000, 200000)).toBe('red');
  });
});
