'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ReviewSession } from '@/components/review/ReviewSession';
import {
  type FlashCard,
  type CardState,
  createCardState,
} from '@/types/card';
import {
  getAllCards,
  getAllCardStates,
  saveCardState,
  saveReviewSession,
} from '@/lib/cache/client-cache';
import { buildReviewQueue, getDueCards } from '@/lib/spaced-repetition/review-queue';
import { DEFAULT_REVIEW_CONFIG } from '@/types/review';

// Sample cards for demo (will be replaced with IndexedDB data)
const SAMPLE_CARDS: FlashCard[] = [
  {
    id: 'sample-1',
    transcriptId: 'transcript-1',
    question: 'What is the purpose of a supervisory organization in Workday?',
    answer: 'A supervisory organization represents a team structure and defines the reporting relationship between workers and their managers. It is used to control access, security, and business processes.',
    category: 'HCM',
    conceptType: 'definition',
    difficulty: 'medium',
    createdAt: new Date().toISOString(),
  },
  {
    id: 'sample-2',
    transcriptId: 'transcript-1',
    question: 'How do you initiate a job change for a worker in Workday?',
    answer: 'Navigate to the worker profile, select Related Actions from the action bar, then choose Job Change. Complete the required fields including effective date, position, and compensation changes.',
    category: 'HCM',
    conceptType: 'procedure',
    difficulty: 'medium',
    createdAt: new Date().toISOString(),
  },
  {
    id: 'sample-3',
    transcriptId: 'transcript-2',
    question: 'What is the difference between a prospect and a candidate in Workday Recruiting?',
    answer: 'A prospect is a potential candidate who has been identified but has not applied for a job. A candidate is someone who has submitted an application for a specific job requisition.',
    category: 'Recruiting',
    conceptType: 'comparison',
    difficulty: 'easy',
    createdAt: new Date().toISOString(),
  },
  {
    id: 'sample-4',
    transcriptId: 'transcript-3',
    question: 'Where can you find the Discovery Boards feature in Workday?',
    answer: 'Discovery Boards can be accessed from the Analytics application or through the search bar by typing "Discovery Boards". They provide visual data exploration with drag-and-drop capabilities.',
    category: 'Analytics',
    conceptType: 'fact',
    difficulty: 'easy',
    createdAt: new Date().toISOString(),
  },
  {
    id: 'sample-5',
    transcriptId: 'transcript-4',
    question: 'What are the steps to create a new learning course in Workday Learning?',
    answer: 'Go to Learning Admin, select Create Course, enter course details (title, description, category), add lessons and media content, configure enrollment settings, and publish the course.',
    category: 'Learning',
    conceptType: 'procedure',
    difficulty: 'hard',
    createdAt: new Date().toISOString(),
  },
];

export default function ReviewPage() {
  const [cards, setCards] = useState<FlashCard[]>([]);
  const [cardStates, setCardStates] = useState<Map<string, CardState>>(new Map());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load cards from IndexedDB (or use sample cards)
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Try to load from IndexedDB
      const [storedCards, storedStates] = await Promise.all([
        getAllCards(),
        getAllCardStates(),
      ]);

      if (storedCards.length > 0) {
        // Build review queue
        const stateMap = new Map(storedStates.map((s) => [s.cardId, s]));
        const queue = buildReviewQueue(storedStates, DEFAULT_REVIEW_CONFIG);

        // Get cards for review session
        const dueCardIds = new Set([
          ...queue.dueCards,
          ...queue.newCards.slice(0, 10), // Limit new cards
          ...queue.learningCards,
        ]);

        const reviewCards = storedCards.filter((c) => dueCardIds.has(c.id));

        setCards(reviewCards);
        setCardStates(stateMap);
      } else {
        // Use sample cards for demo
        const sampleStates = new Map(
          SAMPLE_CARDS.map((c) => [c.id, createCardState(c.id)])
        );

        setCards(SAMPLE_CARDS);
        setCardStates(sampleStates);
      }
    } catch (err) {
      console.error('Failed to load cards:', err);
      setError('Failed to load cards. Using sample data.');

      // Fallback to sample cards
      const sampleStates = new Map(
        SAMPLE_CARDS.map((c) => [c.id, createCardState(c.id)])
      );
      setCards(SAMPLE_CARDS);
      setCardStates(sampleStates);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle card state updates
  const handleCardReviewed = useCallback(
    async (cardId: string, newState: CardState) => {
      try {
        await saveCardState(newState);
        setCardStates((prev) => new Map(prev).set(cardId, newState));
      } catch (err) {
        console.error('Failed to save card state:', err);
      }
    },
    []
  );

  // Handle session completion
  const handleSessionComplete = useCallback(
    async (results: {
      session: any;
      cardResults: any[];
      updatedStates: CardState[];
    }) => {
      try {
        await saveReviewSession(results.session);
        console.log('Session saved:', results.session);
      } catch (err) {
        console.error('Failed to save session:', err);
      }
    },
    []
  );

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Loading cards...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <Button variant="ghost" asChild className="mb-4">
          <Link href="/">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Link>
        </Button>

        <h1 className="text-3xl font-bold">Review Session</h1>
        <p className="text-muted-foreground mt-2">
          {cards.length} cards ready for review
        </p>

        {error && (
          <p className="text-sm text-yellow-600 mt-2">{error}</p>
        )}
      </div>

      {/* Review Session */}
      <ReviewSession
        cards={cards}
        cardStates={cardStates}
        onComplete={handleSessionComplete}
        onCardReviewed={handleCardReviewed}
      />
    </div>
  );
}
