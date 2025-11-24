import { PROBLEM_RANGES } from './constants';

/**
 * Generates a random math problem based on the given operation
 * @param {string} operation - 'addition', 'subtraction', or 'multiplication'
 * @returns {Object} Problem object with operand1, operand2, correctAnswer, operation
 */
export function generateProblem(operation) {
  let operand1, operand2, correctAnswer;

  switch (operation) {
    case 'addition': {
      // Operands: 0-20, result ≤ 25
      const { min, max, maxResult } = PROBLEM_RANGES.addition;
      operand1 = Math.floor(Math.random() * (max - min + 1)) + min;
      // Ensure result doesn't exceed maxResult
      const maxOperand2 = Math.min(max, maxResult - operand1);
      operand2 = Math.floor(Math.random() * (maxOperand2 - min + 1)) + min;
      correctAnswer = operand1 + operand2;
      break;
    }

    case 'subtraction': {
      // Ensure result ≥ 0 (no negatives!)
      // Generate larger number first, subtract smaller
      const { min, max } = PROBLEM_RANGES.subtraction;
      operand1 = Math.floor(Math.random() * (max - min + 1)) + min;
      // operand2 can be at most operand1 to avoid negatives
      operand2 = Math.floor(Math.random() * (operand1 - min + 1)) + min;
      correctAnswer = operand1 - operand2;
      break;
    }

    case 'multiplication': {
      // Operands: 1-5 range only
      const { min, max } = PROBLEM_RANGES.multiplication;
      operand1 = Math.floor(Math.random() * (max - min + 1)) + min;
      operand2 = Math.floor(Math.random() * (max - min + 1)) + min;
      correctAnswer = operand1 * operand2;
      break;
    }

    default:
      throw new Error(`Unknown operation: ${operation}`);
  }

  return {
    operation,
    operand1,
    operand2,
    correctAnswer
  };
}

/**
 * Selects a random operation type
 * @returns {string} One of 'addition', 'subtraction', or 'multiplication'
 */
export function selectRandomOperation() {
  // Equal probability: 33.3% each
  const operations = ['addition', 'subtraction', 'multiplication'];
  return operations[Math.floor(Math.random() * operations.length)];
}

/**
 * Gets the symbol for a given operation
 * @param {string} operation - The operation type
 * @returns {string} The mathematical symbol
 */
export function getOperationSymbol(operation) {
  switch (operation) {
    case 'addition':
      return '+';
    case 'subtraction':
      return '-';
    case 'multiplication':
      return '×';
    default:
      return '?';
  }
}

/**
 * Gets the word for a given operation (for accessibility)
 * @param {string} operation - The operation type
 * @returns {string} The operation name
 */
export function getOperationWord(operation) {
  switch (operation) {
    case 'addition':
      return 'plus';
    case 'subtraction':
      return 'minus';
    case 'multiplication':
      return 'times';
    default:
      return 'equals';
  }
}
