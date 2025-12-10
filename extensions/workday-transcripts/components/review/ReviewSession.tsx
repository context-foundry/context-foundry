'use client';

import { useState, useCallback, useEffect } from 'react';
import { FlashCard } from '@/components/flashcard/FlashCard';
import { RatingButtons } from '@/components/flashcard/RatingButtons';
import { CardProgress } from '@/components/flashcard/CardProgress';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowRight, X } from 'lucide-react';
import type { FlashCard as FlashCardType, CardState, SimpleRating, CardWithState } from '@/types/card';
import type { ReviewSession as ReviewSessionType, ReviewQueueState } from '@/types/review';
import { calculateNextReviewSimple } from '@/lib/spaced-repetition/sm2-algorithm';
import {
  buildReviewQueue,
  getNextCardId,
  removeCardFromQueue,
  getQueueStats,
  mergeCardWithState,
} from '@/lib/spaced-repetition/review-queue';
import { createReviewSession, calculateSessionStats } from '@/types/review';

interface ReviewSessionProps {
  flashcards: FlashCardType[];
  cardStates: Map<string, CardState>;
  onComplete: (session: ReviewSessionType) => void;
  onCardUpdate: (cardId: string, newState: CardState) => void;
  onCancel: () => void;
}

type SessionPhase = 'ready' | 'question' | 'answer' | 'complete';

export function ReviewSession({
  flashcards,
  cardStates,
  onComplete,
  onCardUpdate,
  onCancel,
}: ReviewSessionProps) {
  const [phase, setPhase] = useState<SessionPhase>('ready');
  const [queue, setQueue] = useState<ReviewQueueState | null>(null);
  const [currentCard, setCurrentCard] = useState<CardWithState | null>(null);
  const [session, setSession] = useState<ReturnType<typeof createReviewSession>>(createReviewSession());
  const [startTime] = useState(Date.now());

  // Build queue on mount
  useEffect(() => {
    const states = Array.from(cardStates.values());
    const newQueue = buildReviewQueue(states);
    setQueue(newQueue);
  }, [cardStates]);

  // Load next card when queue changes
  useEffect(() => {
    if (!queue || phase === 'complete') return;

    const nextCardId = getNextCardId(queue);
    if (!nextCardId) {
      handleSessionComplete();
      return;
    }

    const flashcard = flashcards.find((c) => c.id === nextCardId);
    const state = cardStates.get(nextCardId);

    if (flashcard && state) {
      setCurrentCard(mergeCardWithState(flashcard, state));
      if (phase === 'ready') setPhase('question');
    }
  }, [queue, flashcards, cardStates, phase]);

  const handleFlip = useCallback(() => {
    setPhase('answer');
  }, []);

  const handleRate = useCallback(
    (rating: SimpleRating) => {
      if (!currentCard || !queue) return;

      const currentState = cardStates.get(currentCard.id);
      if (!currentState) return;

      // Calculate new card state
      const newState = calculateNextReviewSimple(currentState, rating);
      const wasCorrect = rating !== 'again';

      // Update card state
      onCardUpdate(currentCard.id, newState);

      // Record result in session
      const result = {
        cardId: currentCard.id,
        quality: wasCorrect ? 4 : 0,
        responseTimeMs: 0,
        previousInterval: currentState.interval,
        newInterval: newState.interval,
        previousEaseFactor: currentState.easeFactor,
        newEaseFactor: newState.easeFactor,
        wasCorrect,
        timestamp: new Date().toISOString(),
      };

      setSession((prev) => ({
        ...prev,
        cardResults: [...prev.cardResults, result],
      }));

      // Update queue
      const newQueue = removeCardFromQueue(queue, currentCard.id, wasCorrect);
      setQueue(newQueue);
      setPhase('question');
    },
    [currentCard, queue, cardStates, onCardUpdate]
  );

  const handleSessionComplete = useCallback(() => {
    const endTime = Date.now();
    const stats = calculateSessionStats(session.cardResults);

    const completedSession: ReviewSessionType = {
      ...session,
      ...stats,
      completedAt: new Date().toISOString(),
      timeSpentSeconds: Math.round((endTime - startTime) / 1000),
      newCardsStudied: session.cardResults.filter((r) => {
        const state = cardStates.get(r.cardId);
        return state?.status === 'new';
      }).length,
      reviewCardsStudied:
        session.cardResults.length -
        session.cardResults.filter((r) => {
          const state = cardStates.get(r.cardId);
          return state?.status === 'new';
        }).length,
    };

    setPhase('complete');
    onComplete(completedSession);
  }, [session, startTime, cardStates, onComplete]);

  const stats = queue ? getQueueStats(queue) : null;

  if (phase === 'ready' || !currentCard) {
    return (
      <Card className="max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle>Loading Review Session...</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">Preparing your cards...</p>
        </CardContent>
      </Card>
    );
  }

  if (phase === 'complete') {
    return (
      <Card className="max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle>Session Complete!</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            Great job! You&apos;ve completed your review session.
          </p>
          {stats && (
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-2xl font-bold">{stats.reviewed}</p>
                <p className="text-sm text-muted-foreground">Cards Reviewed</p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-2xl font-bold">{stats.accuracy}%</p>
                <p className="text-sm text-muted-foreground">Accuracy</p>
              </div>
            </div>
          )}
          <Button onClick={onCancel} className="w-full">
            Return to Dashboard
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Progress bar */}
      {stats && (
        <CardProgress
          current={stats.reviewed}
          total={stats.total}
          correct={stats.correct}
        />
      )}

      {/* Cancel button */}
      <div className="flex justify-end">
        <Button variant="ghost" size="sm" onClick={onCancel}>
          <X className="w-4 h-4 mr-1" />
          End Session
        </Button>
      </div>

      {/* Flashcard */}
      <FlashCard
        card={currentCard}
        showAnswer={phase === 'answer'}
        onFlip={handleFlip}
      />

      {/* Rating buttons - only show when answer is revealed */}
      {phase === 'answer' && (
        <RatingButtons
          cardState={{
            cardId: currentCard.id,
            easeFactor: currentCard.easeFactor,
            interval: currentCard.interval,
            repetitions: currentCard.repetitions,
            nextReviewDate: currentCard.nextReviewDate,
            status: currentCard.status,
            totalReviews: currentCard.totalReviews,
            correctStreak: currentCard.correctStreak,
            createdAt: currentCard.createdAt,
            updatedAt: currentCard.updatedAt,
          }}
          onRate={handleRate}
        />
      )}

      {/* Show answer button when in question phase */}
      {phase === 'question' && (
        <Button onClick={handleFlip} className="w-full" size="lg">
          Show Answer
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      )}
    </div>
  );
}

export default ReviewSession;
