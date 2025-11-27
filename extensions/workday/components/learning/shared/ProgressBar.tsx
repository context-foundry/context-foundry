'use client';

import React from 'react';
import * as Progress from '@radix-ui/react-progress';

interface ProgressBarProps {
  value: number; // 0-100
  className?: string;
  showLabel?: boolean;
  label?: string;
}

export function ProgressBar({
  value,
  className = '',
  showLabel = false,
  label,
}: ProgressBarProps) {
  const clampedValue = Math.min(Math.max(value, 0), 100);

  return (
    <div className="w-full">
      {showLabel && (
        <div className="flex items-center justify-between mb-2">
          {label && <span className="text-sm font-medium text-gray-700">{label}</span>}
          <span className="text-sm text-gray-600">{Math.round(clampedValue)}%</span>
        </div>
      )}

      <Progress.Root
        className={`relative overflow-hidden bg-gray-200 rounded-full ${className}`}
        value={clampedValue}
        aria-label={label || 'Progress'}
      >
        <Progress.Indicator
          className="h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-transform duration-300 ease-out"
          style={{ transform: `translateX(-${100 - clampedValue}%)` }}
        />
      </Progress.Root>
    </div>
  );
}
