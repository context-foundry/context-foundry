'use client';

import React from 'react';
import * as Progress from '@radix-ui/react-progress';

interface CompletionChartProps {
  completed: number;
  total: number;
}

export function CompletionChart({ completed, total }: CompletionChartProps) {
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

  // Calculate segments for visual representation
  const segments = [
    { label: 'Completed', count: completed, color: 'bg-green-500' },
    { label: 'Remaining', count: total - completed, color: 'bg-gray-200' },
  ];

  return (
    <div className="space-y-6">
      {/* Radial Progress (using percentage display) */}
      <div className="flex items-center justify-center">
        <div className="relative w-48 h-48">
          {/* Circular progress using conic gradient */}
          <div
            className="w-full h-full rounded-full flex items-center justify-center"
            style={{
              background: `conic-gradient(
                #10b981 0deg ${percentage * 3.6}deg,
                #e5e7eb ${percentage * 3.6}deg 360deg
              )`,
            }}
          >
            <div className="w-36 h-36 bg-white rounded-full flex items-center justify-center shadow-inner">
              <div className="text-center">
                <div className="text-4xl font-bold text-gray-900">{percentage}%</div>
                <div className="text-sm text-gray-600">Complete</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="text-center p-4 bg-green-50 rounded-lg border border-green-200">
          <div className="text-3xl font-bold text-green-600">{completed}</div>
          <div className="text-sm text-gray-600 mt-1">Completed</div>
        </div>
        <div className="text-center p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div className="text-3xl font-bold text-gray-600">{total - completed}</div>
          <div className="text-sm text-gray-600 mt-1">Remaining</div>
        </div>
      </div>

      {/* Linear Progress Bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-700">Overall Progress</span>
          <span className="font-medium text-gray-900">
            {completed} / {total}
          </span>
        </div>
        <Progress.Root
          className="relative overflow-hidden bg-gray-200 rounded-full h-4"
          value={percentage}
          aria-label="Overall completion progress"
        >
          <Progress.Indicator
            className="h-full bg-gradient-to-r from-green-500 to-green-600 transition-transform duration-500 ease-out"
            style={{ transform: `translateX(-${100 - percentage}%)` }}
          />
        </Progress.Root>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-green-500 rounded"></div>
          <span className="text-gray-700">Completed ({completed})</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-gray-200 rounded"></div>
          <span className="text-gray-700">Remaining ({total - completed})</span>
        </div>
      </div>
    </div>
  );
}
