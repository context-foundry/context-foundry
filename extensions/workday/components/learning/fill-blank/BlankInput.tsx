'use client';

import React, { useState } from 'react';
import { HelpCircle, CheckCircle2, XCircle } from 'lucide-react';

interface BlankInputProps {
  blankId: string;
  value: string;
  onChange: (blankId: string, value: string) => void;
  isCorrect: boolean | null;
  disabled?: boolean;
  hint?: string;
}

export function BlankInput({
  blankId,
  value,
  onChange,
  isCorrect,
  disabled = false,
  hint,
}: BlankInputProps) {
  const [showHint, setShowHint] = useState(false);

  const getInputClassName = (): string => {
    const baseClasses =
      'inline-block mx-1 px-3 py-1 border-b-2 min-w-[120px] text-center focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors';

    if (isCorrect === true) {
      return `${baseClasses} border-green-500 bg-green-50 text-green-900`;
    }

    if (isCorrect === false) {
      return `${baseClasses} border-red-500 bg-red-50 text-red-900`;
    }

    if (disabled) {
      return `${baseClasses} border-gray-300 bg-gray-50 text-gray-700 cursor-not-allowed`;
    }

    return `${baseClasses} border-blue-400 bg-white text-gray-900`;
  };

  return (
    <span className="inline-flex items-center gap-1 relative group">
      {/* Input Field */}
      <input
        type="text"
        id={blankId}
        value={value}
        onChange={(e) => onChange(blankId, e.target.value)}
        disabled={disabled}
        className={getInputClassName()}
        aria-label="Fill in the blank"
        aria-describedby={hint ? `${blankId}-hint` : undefined}
      />

      {/* Validation Icon */}
      {isCorrect !== null && (
        <span className="inline-flex items-center">
          {isCorrect ? (
            <CheckCircle2 className="h-4 w-4 text-green-600" aria-label="Correct" />
          ) : (
            <XCircle className="h-4 w-4 text-red-600" aria-label="Incorrect" />
          )}
        </span>
      )}

      {/* Hint Button */}
      {hint && !disabled && (
        <button
          type="button"
          onClick={() => setShowHint(!showHint)}
          className="inline-flex items-center justify-center w-5 h-5 text-blue-600 hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-full"
          aria-label="Show hint"
          aria-expanded={showHint}
        >
          <HelpCircle className="h-4 w-4" aria-hidden="true" />
        </button>
      )}

      {/* Hint Tooltip */}
      {showHint && hint && (
        <span
          id={`${blankId}-hint`}
          className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg whitespace-nowrap z-10"
          role="tooltip"
        >
          {hint}
          <span className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1 border-4 border-transparent border-t-gray-900" />
        </span>
      )}
    </span>
  );
}
