'use client';

import React from 'react';
import { DecisionOption } from '@/types/learning';
import { ArrowRight } from 'lucide-react';

interface DecisionPointProps {
  options: DecisionOption[];
  onSelectOption: (nextNodeId: string, isCorrect: boolean) => void;
}

export function DecisionPoint({ options, onSelectOption }: DecisionPointProps) {
  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        What do you do?
      </h3>

      <div className="space-y-3" role="radiogroup" aria-label="Decision options">
        {options.map((option) => (
          <button
            key={option.id}
            onClick={() => onSelectOption(option.nextNodeId, option.isCorrect ?? false)}
            className="w-full text-left px-5 py-4 rounded-lg border-2 border-gray-300 bg-white hover:border-blue-500 hover:bg-blue-50 transition-all group min-h-[44px] focus:outline-none focus:ring-2 focus:ring-blue-500"
            role="radio"
            aria-checked="false"
            aria-label={option.text}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-gray-900 group-hover:text-blue-900 font-medium">
                {option.text}
              </span>
              <ArrowRight
                className="h-5 w-5 text-gray-400 group-hover:text-blue-600 flex-shrink-0"
                aria-hidden="true"
              />
            </div>

            {/* Rationale (if provided) */}
            {option.rationale && (
              <p className="mt-2 text-sm text-gray-600 group-hover:text-blue-800">
                {option.rationale}
              </p>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
