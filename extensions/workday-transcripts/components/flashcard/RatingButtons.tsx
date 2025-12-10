'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { type SimpleRating, type CardState, RATING_TO_QUALITY } from '@/types/card';
import { previewInterval, formatInterval } from '@/lib/spaced-repetition/sm2-algorithm';

interface RatingButtonsProps {
  cardState: CardState;
  onRate: (rating: SimpleRating) => void;
  disabled?: boolean;
  className?: string;
}

/**
 * Rating buttons for SM-2 quality assessment
 * Maps simplified ratings to SM-2 scale: Again(0), Hard(2), Good(4), Easy(5)
 */
export function RatingButtons({
  cardState,
  onRate,
  disabled = false,
  className,
}: RatingButtonsProps) {
  // Calculate preview intervals for each rating
  const intervals = {
    again: formatInterval(previewInterval(cardState, RATING_TO_QUALITY.again)),
    hard: formatInterval(previewInterval(cardState, RATING_TO_QUALITY.hard)),
    good: formatInterval(previewInterval(cardState, RATING_TO_QUALITY.good)),
    easy: formatInterval(previewInterval(cardState, RATING_TO_QUALITY.easy)),
  };

  const ratings: Array<{
    key: SimpleRating;
    label: string;
    description: string;
    variant: 'again' | 'hard' | 'good' | 'easy';
    shortcut: string;
  }> = [
    {
      key: 'again',
      label: 'Again',
      description: "Didn't know",
      variant: 'again',
      shortcut: '1',
    },
    {
      key: 'hard',
      label: 'Hard',
      description: 'Struggled',
      variant: 'hard',
      shortcut: '2',
    },
    {
      key: 'good',
      label: 'Good',
      description: 'Remembered',
      variant: 'good',
      shortcut: '3',
    },
    {
      key: 'easy',
      label: 'Easy',
      description: 'Perfect',
      variant: 'easy',
      shortcut: '4',
    },
  ];

  // Handle keyboard shortcuts
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (disabled) return;

      const keyToRating: Record<string, SimpleRating> = {
        '1': 'again',
        '2': 'hard',
        '3': 'good',
        '4': 'easy',
      };

      if (keyToRating[e.key]) {
        e.preventDefault();
        onRate(keyToRating[e.key]);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [disabled, onRate]);

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      <p className="text-center text-sm text-muted-foreground">
        How well did you remember this?
      </p>

      <div className="grid grid-cols-4 gap-2">
        {ratings.map((rating) => (
          <Button
            key={rating.key}
            variant={rating.variant}
            size="rating"
            onClick={() => onRate(rating.key)}
            disabled={disabled}
            className="flex flex-col h-auto py-3 gap-1"
          >
            <span className="font-semibold">{rating.label}</span>
            <span className="text-xs opacity-80">{intervals[rating.key]}</span>
            <span className="text-[10px] opacity-60">({rating.shortcut})</span>
          </Button>
        ))}
      </div>

      <p className="text-center text-xs text-muted-foreground">
        Press 1-4 for keyboard shortcuts
      </p>
    </div>
  );
}

export default RatingButtons;
