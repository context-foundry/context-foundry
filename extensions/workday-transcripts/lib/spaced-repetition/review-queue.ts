/**
 * Review Queue Manager
 *
 * Manages the queue of cards for a review session, including:
 * - Filtering due cards
 * - Prioritizing overdue cards
 * - Limiting new cards per day
 * - Interleaving card types
 */

import { type CardState } from '@/types/card';
import {
  type ReviewQueueConfig,
  type ReviewQueueState,
  DEFAULT_REVIEW_CONFIG,
} from '@/types/review';
import { isCardDue, getOverdueDays } from './sm2-algorithm';
import { groupByDueStatus, sortByDueDate } from './scheduler';

/**
 * Get all cards that are due for review
 */
export function getDueCards(
  cards: CardState[],
  referenceDate?: Date
): CardState[] {
  return cards.filter(
    (card) => card.status !== 'suspended' && isCardDue(card, referenceDate)
  );
}

/**
 * Get new cards that haven't been studied yet
 */
export function getNewCards(cards: CardState[]): CardState[] {
  return cards.filter((card) => card.status === 'new');
}

/**
 * Get cards in learning phase (recently failed)
 */
export function getLearningCards(cards: CardState[]): CardState[] {
  return cards.filter((card) => card.status === 'learning');
}

/**
 * Get cards in review phase
 */
export function getReviewCards(cards: CardState[]): CardState[] {
  return cards.filter((card) => card.status === 'review' || card.status === 'graduated');
}

/**
 * Prioritize cards for review
 * Order: Learning (failed) > Overdue > Due today > New
 */
export function prioritizeQueue(
  cards: CardState[],
  config: ReviewQueueConfig = DEFAULT_REVIEW_CONFIG
): CardState[] {
  const { overdue, dueToday } = groupByDueStatus(cards);

  // Learning cards (recently failed) - highest priority
  const learning = cards.filter((c) => c.status === 'learning');

  // Sort overdue by how overdue they are
  const sortedOverdue = [...overdue].sort((a, b) => {
    return getOverdueDays(b) - getOverdueDays(a);
  });

  // Combine in priority order
  const prioritized: CardState[] = [];

  // First: learning cards
  prioritized.push(...sortByDueDate(learning));

  // Second: overdue cards (if showOverdueFirst is enabled)
  if (config.showOverdueFirst) {
    prioritized.push(
      ...sortedOverdue.filter((c) => c.status !== 'learning')
    );
  }

  // Third: due today
  prioritized.push(
    ...dueToday.filter((c) => c.status !== 'learning')
  );

  // If showOverdueFirst is disabled, add overdue after today's cards
  if (!config.showOverdueFirst) {
    prioritized.push(
      ...sortedOverdue.filter((c) => c.status !== 'learning')
    );
  }

  return prioritized;
}

/**
 * Get new cards for today, respecting daily limit
 */
export function getNewCardsForToday(
  cards: CardState[],
  studiedToday: number,
  config: ReviewQueueConfig = DEFAULT_REVIEW_CONFIG
): CardState[] {
  const newCards = getNewCards(cards);
  const remaining = Math.max(0, config.newCardsPerDay - studiedToday);

  return newCards.slice(0, remaining);
}

/**
 * Build a complete review queue for a session
 */
export function buildReviewQueue(
  allCards: CardState[],
  config: ReviewQueueConfig = DEFAULT_REVIEW_CONFIG,
  newCardsStudiedToday: number = 0
): ReviewQueueState {
  const now = new Date().toISOString();

  // Get due cards (learning + review)
  const dueCards = getDueCards(allCards);
  const prioritizedDue = prioritizeQueue(dueCards, config);

  // Get new cards to introduce today
  const newCards = getNewCardsForToday(allCards, newCardsStudiedToday, config);

  // Separate learning cards (they need special handling)
  const learningCards = allCards.filter((c) => c.status === 'learning');

  // Apply max reviews limit
  const totalAvailable = prioritizedDue.length + newCards.length;
  const maxTotal = config.maxReviewsPerDay;

  let dueCardIds = prioritizedDue.map((c) => c.cardId);
  let newCardIds = newCards.map((c) => c.cardId);

  // If we exceed max, prioritize due cards over new
  if (totalAvailable > maxTotal) {
    if (dueCardIds.length >= maxTotal) {
      dueCardIds = dueCardIds.slice(0, maxTotal);
      newCardIds = [];
    } else {
      const remainingSlots = maxTotal - dueCardIds.length;
      newCardIds = newCardIds.slice(0, remainingSlots);
    }
  }

  return {
    dueCards: dueCardIds,
    newCards: newCardIds,
    learningCards: learningCards.map((c) => c.cardId),
    reviewedCount: 0,
    correctCount: 0,
    currentIndex: 0,
    queueBuiltAt: now,
  };
}

/**
 * Get the next card to review from the queue
 */
export function getNextCard(
  queue: ReviewQueueState,
  allCards: CardState[]
): CardState | null {
  // Combine queue in order: learning first, then due, then new
  const allCardIds = [
    ...queue.learningCards,
    ...queue.dueCards,
    ...queue.newCards,
  ];

  // Filter to only unreviewd cards
  const reviewedSet = new Set<string>(); // Would need to track this
  const remaining = allCardIds.filter((id) => !reviewedSet.has(id));

  if (queue.currentIndex >= remaining.length) {
    return null;
  }

  const nextId = remaining[queue.currentIndex];
  return allCards.find((c) => c.cardId === nextId) || null;
}

/**
 * Interleave new cards with review cards
 * This prevents users from seeing all new cards at once
 */
export function interleaveCards(
  dueCards: CardState[],
  newCards: CardState[],
  interval: number = 5
): CardState[] {
  if (newCards.length === 0) return dueCards;
  if (dueCards.length === 0) return newCards;

  const result: CardState[] = [];
  let dueIndex = 0;
  let newIndex = 0;
  let counter = 0;

  while (dueIndex < dueCards.length || newIndex < newCards.length) {
    // Add due cards
    if (dueIndex < dueCards.length) {
      result.push(dueCards[dueIndex]);
      dueIndex++;
      counter++;
    }

    // Every 'interval' cards, add a new card
    if (counter >= interval && newIndex < newCards.length) {
      result.push(newCards[newIndex]);
      newIndex++;
      counter = 0;
    }
  }

  // Add remaining new cards at the end
  while (newIndex < newCards.length) {
    result.push(newCards[newIndex]);
    newIndex++;
  }

  return result;
}

/**
 * Get queue statistics
 */
export function getQueueStats(
  queue: ReviewQueueState
): {
  totalCards: number;
  dueCount: number;
  newCount: number;
  learningCount: number;
  progress: number;
} {
  const totalCards =
    queue.dueCards.length + queue.newCards.length + queue.learningCards.length;

  return {
    totalCards,
    dueCount: queue.dueCards.length,
    newCount: queue.newCards.length,
    learningCount: queue.learningCards.length,
    progress:
      totalCards > 0
        ? Math.round((queue.reviewedCount / totalCards) * 100)
        : 100,
  };
}
