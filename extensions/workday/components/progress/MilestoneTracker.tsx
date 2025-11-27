'use client';

import React from 'react';
import { MILESTONES } from '@/types/progress';
import { CheckCircle2, Circle, Download } from 'lucide-react';
import { ProgressBar } from '../learning/shared/ProgressBar';
import Link from 'next/link';

interface MilestoneTrackerProps {
  currentCount: number;
}

export function MilestoneTracker({ currentCount }: MilestoneTrackerProps) {
  return (
    <div className="space-y-6">
      {MILESTONES.map((milestone) => {
        const completed = currentCount >= milestone.targetCount;
        const progress = Math.min((currentCount / milestone.targetCount) * 100, 100);

        return (
          <div
            key={milestone.id}
            className={`rounded-lg border-2 p-5 transition-all ${
              completed
                ? 'bg-green-50 border-green-300'
                : 'bg-white border-gray-200'
            }`}
          >
            <div className="flex items-start gap-4">
              {/* Icon */}
              <div className="flex-shrink-0 mt-1">
                {completed ? (
                  <CheckCircle2 className="h-8 w-8 text-green-600" aria-hidden="true" />
                ) : (
                  <Circle className="h-8 w-8 text-gray-400" aria-hidden="true" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      {milestone.name}
                    </h3>
                    <p className="text-sm text-gray-600">{milestone.description}</p>
                  </div>

                  {/* Certificate Badge */}
                  {completed && milestone.certificateEligible && (
                    <Link
                      href={`/certificate?milestone=${milestone.id}`}
                      className="flex-shrink-0 inline-flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 transition-colors min-h-[44px]"
                      aria-label={`Download certificate for ${milestone.name}`}
                    >
                      <Download className="h-3 w-3" aria-hidden="true" />
                      Certificate
                    </Link>
                  )}
                </div>

                {/* Progress */}
                <div className="mt-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-700">
                      {currentCount} / {milestone.targetCount} patterns
                    </span>
                    <span className="text-sm font-medium text-gray-900">
                      {Math.round(progress)}%
                    </span>
                  </div>
                  <ProgressBar value={progress} className="h-2" />
                </div>

                {/* Status */}
                {completed ? (
                  <div className="mt-3 flex items-center gap-2 text-sm text-green-700">
                    <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                    <span className="font-medium">Completed!</span>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-gray-600">
                    {milestone.targetCount - currentCount} more to go
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
