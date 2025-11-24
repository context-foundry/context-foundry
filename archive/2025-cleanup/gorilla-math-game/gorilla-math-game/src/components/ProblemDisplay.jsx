import React from 'react';
import { getOperationSymbol, getOperationWord } from '../utils/problemGenerator';

/**
 * ProblemDisplay Component
 * Displays the current math problem in large, kid-friendly format
 */
export default function ProblemDisplay({ operation, operand1, operand2 }) {
  const symbol = getOperationSymbol(operation);
  const word = getOperationWord(operation);

  // Color code operation symbols
  const getSymbolColor = (op) => {
    switch (op) {
      case 'addition':
        return 'text-green-600';
      case 'subtraction':
        return 'text-red-600';
      case 'multiplication':
        return 'text-blue-600';
      default:
        return 'text-gray-800';
    }
  };

  const ariaLabel = `Math problem: ${operand1} ${word} ${operand2} equals what?`;

  return (
    <div
      className="bg-yellow-50 border-4 border-yellow-400 rounded-3xl p-8 md:p-12 shadow-xl"
      aria-label={ariaLabel}
      role="region"
    >
      <div className="flex items-center justify-center gap-4 md:gap-8 text-5xl md:text-7xl font-bold">
        <span className="text-gray-800">{operand1}</span>
        <span className={getSymbolColor(operation)}>{symbol}</span>
        <span className="text-gray-800">{operand2}</span>
        <span className="text-purple-600">=</span>
        <span className="text-orange-600">?</span>
      </div>
    </div>
  );
}
