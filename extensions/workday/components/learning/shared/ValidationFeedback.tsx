'use client';

import React from 'react';
import { CheckCircle2, XCircle, AlertCircle } from 'lucide-react';

interface ValidationFeedbackProps {
  isCorrect: boolean;
  message?: string;
  explanation?: string;
  relatedBestPractices?: string[];
}

export function ValidationFeedback({
  isCorrect,
  message,
  explanation,
  relatedBestPractices,
}: ValidationFeedbackProps) {
  const Icon = isCorrect ? CheckCircle2 : XCircle;
  const bgColor = isCorrect ? 'bg-green-50' : 'bg-red-50';
  const borderColor = isCorrect ? 'border-green-200' : 'border-red-200';
  const textColor = isCorrect ? 'text-green-900' : 'text-red-900';
  const iconColor = isCorrect ? 'text-green-600' : 'text-red-600';

  return (
    <div
      className={`rounded-lg border p-4 ${bgColor} ${borderColor}`}
      role="alert"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        <Icon className={`h-6 w-6 flex-shrink-0 mt-0.5 ${iconColor}`} aria-hidden="true" />
        <div className="flex-1 space-y-3">
          {/* Message */}
          {message && (
            <p className={`font-semibold ${textColor}`}>{message}</p>
          )}

          {/* Explanation */}
          {explanation && (
            <p className="text-sm text-gray-700 leading-relaxed">{explanation}</p>
          )}

          {/* Related Best Practices */}
          {relatedBestPractices && relatedBestPractices.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="h-4 w-4 text-blue-600" aria-hidden="true" />
                <h4 className="text-sm font-semibold text-gray-900">
                  Related Best Practices
                </h4>
              </div>
              <ul className="space-y-1 ml-6" role="list">
                {relatedBestPractices.map((practice, index) => (
                  <li key={index} className="text-sm text-gray-700">
                    {practice}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
