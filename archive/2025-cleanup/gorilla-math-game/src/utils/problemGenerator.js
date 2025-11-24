/**
 * Problem Generator Utilities
 * Pure functions for generating random math problems for 2nd graders
 */

/**
 * Generate random integer between min and max (inclusive)
 * @param {number} min - Minimum value
 * @param {number} max - Maximum value
 * @returns {number} Random integer
 */
function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

/**
 * Generate addition problem (result <= 25)
 * @returns {Object} Problem object with operand1, operand2, operator, correctAnswer
 */
export function generateAddition() {
  const operand1 = randomInt(0, 20);
  const operand2 = randomInt(0, Math.min(20, 25 - operand1));
  return {
    operand1,
    operand2,
    operator: '+',
    correctAnswer: operand1 + operand2
  };
}

/**
 * Generate subtraction problem (result >= 0)
 * @returns {Object} Problem object with operand1, operand2, operator, correctAnswer
 */
export function generateSubtraction() {
  const correctAnswer = randomInt(0, 20);
  const operand2 = randomInt(0, 20);
  const operand1 = correctAnswer + operand2;
  return {
    operand1,
    operand2,
    operator: '-',
    correctAnswer
  };
}

/**
 * Generate multiplication problem (operands 1-5)
 * @returns {Object} Problem object with operand1, operand2, operator, correctAnswer
 */
export function generateMultiplication() {
  const operand1 = randomInt(1, 5);
  const operand2 = randomInt(1, 5);
  return {
    operand1,
    operand2,
    operator: '×',
    correctAnswer: operand1 * operand2
  };
}

/**
 * Select random problem type and generate it
 * @returns {Object} Problem object with operand1, operand2, operator, correctAnswer
 */
export function generateRandomProblem() {
  const types = [generateAddition, generateSubtraction, generateMultiplication];
  const selected = types[randomInt(0, types.length - 1)];
  return selected();
}
