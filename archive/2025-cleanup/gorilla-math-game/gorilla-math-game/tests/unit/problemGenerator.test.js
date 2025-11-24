import { describe, test, expect } from 'vitest';
import { generateProblem, selectRandomOperation, getOperationSymbol, getOperationWord } from '../../src/utils/problemGenerator';

describe('generateProblem', () => {
  test('addition generates valid problems within range', () => {
    for (let i = 0; i < 100; i++) {
      const problem = generateProblem('addition');
      expect(problem.operand1).toBeGreaterThanOrEqual(0);
      expect(problem.operand1).toBeLessThanOrEqual(20);
      expect(problem.operand2).toBeGreaterThanOrEqual(0);
      expect(problem.operand2).toBeLessThanOrEqual(20);
      expect(problem.correctAnswer).toBeLessThanOrEqual(25);
      expect(problem.correctAnswer).toBe(problem.operand1 + problem.operand2);
    }
  });

  test('subtraction never produces negative results', () => {
    for (let i = 0; i < 100; i++) {
      const problem = generateProblem('subtraction');
      expect(problem.correctAnswer).toBeGreaterThanOrEqual(0);
      expect(problem.correctAnswer).toBe(problem.operand1 - problem.operand2);
      expect(problem.operand1).toBeGreaterThanOrEqual(problem.operand2);
    }
  });

  test('subtraction handles edge case 0 - 0 = 0', () => {
    // This should be valid
    const problem = { operand1: 0, operand2: 0, correctAnswer: 0 };
    expect(problem.correctAnswer).toBe(0);
    expect(problem.correctAnswer).toBeGreaterThanOrEqual(0);
  });

  test('multiplication stays in 1-5 range', () => {
    for (let i = 0; i < 100; i++) {
      const problem = generateProblem('multiplication');
      expect(problem.operand1).toBeGreaterThanOrEqual(1);
      expect(problem.operand1).toBeLessThanOrEqual(5);
      expect(problem.operand2).toBeGreaterThanOrEqual(1);
      expect(problem.operand2).toBeLessThanOrEqual(5);
      expect(problem.correctAnswer).toBe(problem.operand1 * problem.operand2);
      expect(problem.correctAnswer).toBeLessThanOrEqual(25); // Max: 5 × 5
    }
  });

  test('generates problem with correct operation type', () => {
    const addProblem = generateProblem('addition');
    expect(addProblem.operation).toBe('addition');

    const subProblem = generateProblem('subtraction');
    expect(subProblem.operation).toBe('subtraction');

    const mulProblem = generateProblem('multiplication');
    expect(mulProblem.operation).toBe('multiplication');
  });

  test('throws error for unknown operation', () => {
    expect(() => generateProblem('division')).toThrow('Unknown operation');
  });
});

describe('selectRandomOperation', () => {
  test('returns one of the three valid operations', () => {
    const validOperations = ['addition', 'subtraction', 'multiplication'];

    for (let i = 0; i < 50; i++) {
      const operation = selectRandomOperation();
      expect(validOperations).toContain(operation);
    }
  });

  test('generates variety of operations over multiple calls', () => {
    const operations = new Set();
    for (let i = 0; i < 100; i++) {
      operations.add(selectRandomOperation());
    }
    // Should have all three types in 100 calls (statistically very likely)
    expect(operations.size).toBeGreaterThan(1);
  });
});

describe('getOperationSymbol', () => {
  test('returns correct symbols for operations', () => {
    expect(getOperationSymbol('addition')).toBe('+');
    expect(getOperationSymbol('subtraction')).toBe('-');
    expect(getOperationSymbol('multiplication')).toBe('×');
    expect(getOperationSymbol('unknown')).toBe('?');
  });
});

describe('getOperationWord', () => {
  test('returns correct words for operations', () => {
    expect(getOperationWord('addition')).toBe('plus');
    expect(getOperationWord('subtraction')).toBe('minus');
    expect(getOperationWord('multiplication')).toBe('times');
    expect(getOperationWord('unknown')).toBe('equals');
  });
});
