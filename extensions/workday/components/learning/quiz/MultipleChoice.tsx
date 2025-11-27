'use client';

import React from 'react';
import { QuizQuestion } from '@/types/learning';

interface MultipleChoiceProps {
  question: QuizQuestion;
  selectedAnswer: number | undefined;
  onAnswerSelect: (answerIndex: number) => void;
  showFeedback?: boolean;
  disabled?: boolean;
}

export function MultipleChoice({
  question,
  selectedAnswer,
  onAnswerSelect,
  showFeedback = false,
  disabled = false,
}: MultipleChoiceProps) {
  const getOptionClassName = (index: number): string => {
    const baseClasses =
      'w-full text-left px-4 py-3 rounded-lg border-2 transition-all min-h-[44px] focus:outline-none focus:ring-2 focus:ring-blue-500';

    if (disabled || showFeedback) {
      if (showFeedback) {
        if (index === question.correctAnswer) {
          return `${baseClasses} border-green-500 bg-green-50 text-green-900`;
        }
        if (index === selectedAnswer && index !== question.correctAnswer) {
          return `${baseClasses} border-red-500 bg-red-50 text-red-900`;
        }
      }
      return `${baseClasses} border-gray-300 bg-gray-50 text-gray-700 cursor-not-allowed`;
    }

    if (index === selectedAnswer) {
      return `${baseClasses} border-blue-600 bg-blue-50 text-blue-900 font-medium`;
    }

    return `${baseClasses} border-gray-300 bg-white text-gray-900 hover:border-blue-400 hover:bg-blue-50`;
  };

  const getOptionLabel = (index: number): string => {
    return String.fromCharCode(65 + index); // A, B, C, D
  };

  return (
    <div className="space-y-4">
      {/* Question */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">{question.question}</h3>
        {question.difficulty && (
          <span className="inline-block px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-700 capitalize">
            {question.difficulty}
          </span>
        )}
      </div>

      {/* Options */}
      <div className="space-y-3" role="radiogroup" aria-label="Answer options">
        {question.options.map((option, index) => {
          const isSelected = index === selectedAnswer;
          const isCorrect = index === question.correctAnswer;
          const isIncorrect = showFeedback && isSelected && !isCorrect;

          return (
            <button
              key={index}
              onClick={() => !disabled && !showFeedback && onAnswerSelect(index)}
              className={getOptionClassName(index)}
              disabled={disabled || showFeedback}
              role="radio"
              aria-checked={isSelected}
              aria-label={`Option ${getOptionLabel(index)}: ${option}`}
            >
              <div className="flex items-center gap-3">
                {/* Option Label */}
                <span className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-sm font-semibold">
                  {getOptionLabel(index)}
                </span>

                {/* Option Text */}
                <span className="flex-1 text-sm">{option}</span>

                {/* Feedback Icons */}
                {showFeedback && (
                  <>
                    {isCorrect && (
                      <span className="flex-shrink-0 text-green-600 font-semibold" aria-label="Correct answer">
                        ✓
                      </span>
                    )}
                    {isIncorrect && (
                      <span className="flex-shrink-0 text-red-600 font-semibold" aria-label="Incorrect answer">
                        ✗
                      </span>
                    )}
                  </>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Explanation */}
      {showFeedback && question.explanation && (
        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h4 className="font-semibold text-blue-900 mb-2">Explanation</h4>
          <p className="text-sm text-blue-800 leading-relaxed">{question.explanation}</p>
        </div>
      )}
    </div>
  );
}
