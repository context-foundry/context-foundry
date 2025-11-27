'use client';

import React from 'react';
import { ScenarioNode } from '@/types/learning';
import { CheckCircle2, XCircle, AlertCircle, RotateCcw, ArrowRight } from 'lucide-react';

interface OutcomeDisplayProps {
  node: ScenarioNode;
  isCompleted: boolean;
  decisionsCorrect: number;
  decisionsTotal: number;
  onContinue?: () => void;
  onRestart?: () => void;
}

export function OutcomeDisplay({
  node,
  isCompleted,
  decisionsCorrect,
  decisionsTotal,
  onContinue,
  onRestart,
}: OutcomeDisplayProps) {
  const isSuccessful = node.isSuccessful ?? false;
  const isEnd = node.type === 'end';

  const getIcon = () => {
    if (isSuccessful) {
      return <CheckCircle2 className="h-16 w-16 text-green-600" aria-hidden="true" />;
    }
    if (isEnd && !isSuccessful) {
      return <XCircle className="h-16 w-16 text-red-600" aria-hidden="true" />;
    }
    return <AlertCircle className="h-16 w-16 text-yellow-600" aria-hidden="true" />;
  };

  const getBackgroundColor = () => {
    if (isSuccessful) {
      return 'bg-gradient-to-br from-green-50 to-green-100 border-green-200';
    }
    if (isEnd && !isSuccessful) {
      return 'bg-gradient-to-br from-red-50 to-red-100 border-red-200';
    }
    return 'bg-gradient-to-br from-yellow-50 to-yellow-100 border-yellow-200';
  };

  const getScoreColor = () => {
    const percentage = decisionsTotal > 0 ? (decisionsCorrect / decisionsTotal) * 100 : 0;
    if (percentage >= 80) return 'text-green-600';
    if (percentage >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className={`rounded-lg border-2 p-8 ${getBackgroundColor()}`}>
        {/* Icon */}
        <div className="flex justify-center mb-6">{getIcon()}</div>

        {/* Title */}
        <h2 className="text-3xl font-bold text-gray-900 text-center mb-4">
          {node.title}
        </h2>

        {/* Description */}
        <div className="mb-6">
          <p className="text-lg text-gray-700 text-center leading-relaxed whitespace-pre-line">
            {node.description}
          </p>
        </div>

        {/* Feedback */}
        {node.feedback && (
          <div className="bg-white rounded-lg p-5 mb-6 border border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-blue-600" aria-hidden="true" />
              Feedback
            </h3>
            <p className="text-gray-700 leading-relaxed">{node.feedback}</p>
          </div>
        )}

        {/* Image (if available) */}
        {node.imageUrl && (
          <div className="mb-6 rounded-lg overflow-hidden border border-gray-200">
            <img
              src={node.imageUrl}
              alt="Scenario outcome illustration"
              className="w-full h-auto"
            />
          </div>
        )}

        {/* Score (for completed scenarios) */}
        {isCompleted && (
          <div className="bg-white rounded-lg p-6 mb-6 text-center">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className={`text-4xl font-bold mb-1 ${getScoreColor()}`}>
                  {decisionsCorrect}/{decisionsTotal}
                </div>
                <div className="text-sm text-gray-600">Correct Decisions</div>
              </div>
              <div>
                <div className="text-4xl font-bold text-blue-600 mb-1">
                  {decisionsTotal > 0
                    ? Math.round((decisionsCorrect / decisionsTotal) * 100)
                    : 0}
                  %
                </div>
                <div className="text-sm text-gray-600">Success Rate</div>
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          {onContinue && !isEnd && (
            <button
              onClick={onContinue}
              className="inline-flex items-center gap-2 px-6 py-3 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Continue scenario"
            >
              Continue
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
          )}

          {onRestart && (
            <button
              onClick={onRestart}
              className="inline-flex items-center gap-2 px-6 py-3 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Restart scenario"
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Restart Scenario
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
