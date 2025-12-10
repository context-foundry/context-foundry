'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { type FlashCard as FlashCardType, type CardState } from '@/types/card';
import { Badge } from '@/components/ui/badge';

interface FlashCardProps {
  card: FlashCardType;
  cardState?: CardState;
  showAnswer: boolean;
  onFlip: () => void;
  className?: string;
}

/**
 * Interactive flashcard component with flip animation
 */
export function FlashCard({
  card,
  cardState,
  showAnswer,
  onFlip,
  className,
}: FlashCardProps) {
  const getCategoryVariant = (category: string) => {
    const variants: Record<string, 'hcm' | 'recruiting' | 'learning' | 'analytics' | 'general'> = {
      HCM: 'hcm',
      Recruiting: 'recruiting',
      Learning: 'learning',
      Analytics: 'analytics',
      General: 'general',
    };
    return variants[category] || 'general';
  };

  const getDifficultyVariant = (difficulty: string) => {
    const variants: Record<string, 'easy' | 'medium' | 'hard'> = {
      easy: 'easy',
      medium: 'medium',
      hard: 'hard',
    };
    return variants[difficulty] || 'medium';
  };

  return (
    <div
      className={cn(
        'perspective-1000 cursor-pointer',
        className
      )}
      onClick={onFlip}
      onKeyDown={(e) => {
        if (e.key === ' ' || e.key === 'Enter') {
          e.preventDefault();
          onFlip();
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={showAnswer ? 'Show question' : 'Show answer'}
    >
      <div
        className={cn(
          'relative w-full min-h-[300px] transition-transform duration-500 transform-style-preserve-3d',
          showAnswer && 'rotate-y-180'
        )}
        style={{
          transformStyle: 'preserve-3d',
          transform: showAnswer ? 'rotateY(180deg)' : 'rotateY(0deg)',
        }}
      >
        {/* Front (Question) */}
        <div
          className={cn(
            'absolute inset-0 w-full h-full backface-hidden',
            'bg-card border border-border rounded-xl shadow-lg',
            'flex flex-col p-6'
          )}
          style={{ backfaceVisibility: 'hidden' }}
        >
          <div className="flex items-center justify-between mb-4">
            <Badge variant={getCategoryVariant(card.category)}>
              {card.category}
            </Badge>
            <Badge variant={getDifficultyVariant(card.difficulty)}>
              {card.difficulty}
            </Badge>
          </div>

          <div className="flex-1 flex items-center justify-center">
            <p className="text-xl text-center font-medium">{card.question}</p>
          </div>

          <div className="text-center text-sm text-muted-foreground mt-4">
            Click or press Space to reveal answer
          </div>
        </div>

        {/* Back (Answer) */}
        <div
          className={cn(
            'absolute inset-0 w-full h-full backface-hidden',
            'bg-card border border-border rounded-xl shadow-lg',
            'flex flex-col p-6'
          )}
          style={{
            backfaceVisibility: 'hidden',
            transform: 'rotateY(180deg)',
          }}
        >
          <div className="flex items-center justify-between mb-4">
            <Badge variant="outline">{card.conceptType}</Badge>
            {cardState && (
              <span className="text-xs text-muted-foreground">
                Reviews: {cardState.totalReviews}
              </span>
            )}
          </div>

          <div className="flex-1 flex flex-col">
            <div className="mb-4">
              <h4 className="text-sm font-medium text-muted-foreground mb-2">
                Question:
              </h4>
              <p className="text-sm">{card.question}</p>
            </div>

            <div className="flex-1 flex items-center">
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">
                  Answer:
                </h4>
                <p className="text-lg">{card.answer}</p>
              </div>
            </div>
          </div>

          <div className="text-center text-sm text-muted-foreground mt-4">
            Rate your recall below
          </div>
        </div>
      </div>
    </div>
  );
}

export default FlashCard;
