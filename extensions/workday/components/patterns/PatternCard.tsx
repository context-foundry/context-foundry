'use client';

import React from 'react';
import Link from 'next/link';
import { CheckCircle2, Clock, TrendingUp } from 'lucide-react';
import { TransformedPattern } from '@/types/pattern';

interface PatternCardProps {
  pattern: TransformedPattern;
}

export function PatternCard({ pattern }: PatternCardProps) {
  const statusColors = {
    'not-started': 'bg-gray-100 text-gray-700',
    'in-progress': 'bg-blue-100 text-blue-700',
    'completed': 'bg-green-100 text-green-700',
  };

  const statusIcons = {
    'not-started': null,
    'in-progress': <TrendingUp className="h-4 w-4" />,
    'completed': <CheckCircle2 className="h-4 w-4" />,
  };

  const status = pattern.completionStatus || 'not-started';

  return (
    <Link
      href={`/patterns/${pattern.id}`}
      className="block group"
      aria-label={`View details for ${pattern.displayName}`}
    >
      <article className="bg-white rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-5 h-full flex flex-col min-h-[44px]">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-900 group-hover:text-blue-600 transition-colors line-clamp-2">
              {pattern.displayName}
            </h3>
            <p className="text-sm text-gray-600 mt-1">{pattern.categoryLabel}</p>
          </div>

          {/* Status Badge */}
          {status !== 'not-started' && (
            <div
              className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${statusColors[status]}`}
              aria-label={`Status: ${status.replace('-', ' ')}`}
            >
              {statusIcons[status]}
              <span className="capitalize">{status.replace('-', ' ')}</span>
            </div>
          )}
        </div>

        {/* Description */}
        <p className="text-sm text-gray-700 mb-4 line-clamp-3 flex-1">
          {pattern.description}
        </p>

        {/* Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-gray-100">
          <div className="flex items-center gap-4 text-xs text-gray-600">
            {/* Difficulty */}
            {pattern.difficulty && (
              <span className="flex items-center gap-1">
                <span className="font-medium">{pattern.difficultyLabel}</span>
              </span>
            )}

            {/* Estimated Time */}
            {pattern.estimated_time_minutes && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" aria-hidden="true" />
                <span>{pattern.estimatedTimeLabel}</span>
              </span>
            )}
          </div>

          {/* Completion Progress */}
          {pattern.completionPercentage !== undefined && pattern.completionPercentage > 0 && (
            <div className="flex items-center gap-2">
              <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 transition-all"
                  style={{ width: `${pattern.completionPercentage}%` }}
                  role="progressbar"
                  aria-valuenow={pattern.completionPercentage}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${pattern.completionPercentage}% complete`}
                />
              </div>
              <span className="text-xs text-gray-600 font-medium">
                {pattern.completionPercentage}%
              </span>
            </div>
          )}
        </div>
      </article>
    </Link>
  );
}
