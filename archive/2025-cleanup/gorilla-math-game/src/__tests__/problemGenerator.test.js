import { describe, it, expect } from 'vitest';
import {
  generateAddition,
  generateSubtraction,
  generateMultiplication,
  generateRandomProblem
} from '../utils/problemGenerator';

describe('Problem Generator', () => {
  it('generates addition problems with result <= 25', () => {
    for (let i = 0; i < 100; i++) {
      const problem = generateAddition();
      expect(problem.correctAnswer).toBeLessThanOrEqual(25);
      expect(problem.correctAnswer).toBeGreaterThanOrEqual(0);
      expect(problem.operator).toBe('+');
      expect(problem.operand1 + problem.operand2).toBe(problem.correctAnswer);
    }
  });

  it('generates subtraction problems with non-negative results', () => {
    for (let i = 0; i < 100; i++) {
      const problem = generateSubtraction();
      expect(problem.correctAnswer).toBeGreaterThanOrEqual(0);
      expect(problem.operand1 - problem.operand2).toBe(problem.correctAnswer);
      expect(problem.operator).toBe('-');
    }
  });

  it('generates multiplication problems with operands 1-5', () => {
    for (let i = 0; i < 100; i++) {
      const problem = generateMultiplication();
      expect(problem.operand1).toBeGreaterThanOrEqual(1);
      expect(problem.operand1).toBeLessThanOrEqual(5);
      expect(problem.operand2).toBeGreaterThanOrEqual(1);
      expect(problem.operand2).toBeLessThanOrEqual(5);
      expect(problem.correctAnswer).toBe(problem.operand1 * problem.operand2);
      expect(problem.operator).toBe('×');
    }
  });

  it('generates random problems from all three types', () => {
    const operators = new Set();
    for (let i = 0; i < 50; i++) {
      const problem = generateRandomProblem();
      operators.add(problem.operator);
    }
    expect(operators.size).toBe(3); // All three operators should appear
  });

  it('generates valid problem objects with all required fields', () => {
    const problem = generateRandomProblem();
    expect(problem).toHaveProperty('operand1');
    expect(problem).toHaveProperty('operand2');
    expect(problem).toHaveProperty('operator');
    expect(problem).toHaveProperty('correctAnswer');
    expect(typeof problem.operand1).toBe('number');
    expect(typeof problem.operand2).toBe('number');
    expect(typeof problem.correctAnswer).toBe('number');
  });
});
