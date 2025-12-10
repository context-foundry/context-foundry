'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { Progress } from '@/components/ui/progress';

interface CardProgressProps {
  current: number;
  total: number;
  correctCount: number;
  className?: string;
}

/**
 * Progress indicator for review session
 */
export function CardProgress({
  current,
  total,
  correctCount,
  className,
}: CardProgressProps) {
  const progressPercent = total > 0 ? Math.round((current / total) * 100) : 0;
  const accuracyPercent = current > 0 ? Math.round((correctCount / current) * 100) : 0;

  return (
    <div className={cn('space-y-3', className)}>
      {/* Card counter */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">Card</span>
        <span className="font-medium">
          {current} / {total}
        </span>
      </div>

      {/* Progress bar */}
      <Progress value={progressPercent} className="h-2" />

      {/* Stats row */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{progressPercent}% complete</span>
        {current > 0 && (
          <span
            className={cn(
              accuracyPercent >= 80
                ? 'text-green-600'
                : accuracyPercent >= 60
                ? 'text-yellow-600'
                : 'text-red-600'
            )}
          >
            {accuracyPercent}% accuracy
          </span>
        )}
      </div>
    </div>
  );
}

export default CardProgress;
