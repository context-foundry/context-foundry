/**
 * SM-2 Spaced Repetition Algorithm Implementation
 *
 * The SM-2 algorithm calculates optimal review intervals based on
 * user-reported recall quality. It adjusts the "ease factor" (EF)
 * for each card based on performance.
 *
 * Quality ratings (0-5):
 * - 0: Complete blackout
 * - 1: Incorrect, but recognized answer
 * - 2: Incorrect, answer seemed easy once seen
 * - 3: Correct with serious difficulty
 * - 4: Correct after hesitation
 * - 5: Perfect instant recall
 *
 * Algorithm:
 * EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
 * where EF' >= 1.3
 *
 * Interval:
 * - rep 0: 1 day
 * - rep 1: 6 days
 * - rep n: previous_interval * EF'
 */

import {
  type CardState,
  type QualityRating,
  SM2_DEFAULTS,
} from '@/types/card';

/**
 * Calculate new ease factor based on quality rating
 * EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
 */
export function calculateEaseFactor(
  currentEF: number,
  quality: QualityRating
): number {
  const newEF = currentEF + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02));

  // Clamp to valid range
  return Math.max(
    SM2_DEFAULTS.MIN_EASE_FACTOR,
    Math.min(SM2_DEFAULTS.MAX_EASE_FACTOR, newEF)
  );
}

/**
 * Calculate next review interval based on repetition count and ease factor
 */
export function calculateInterval(
  repetitions: number,
  easeFactor: number,
  previousInterval: number = 0
): number {
  if (repetitions === 0) {
    return 1; // First successful review: 1 day
  }

  if (repetitions === 1) {
    return 6; // Second successful review: 6 days
  }

  // Subsequent reviews: multiply previous interval by ease factor
  return Math.round(previousInterval * easeFactor);
}

/**
 * Process a card review and return updated card state
 */
export function calculateNextReview(
  card: CardState,
  quality: QualityRating
): CardState {
  const now = new Date();
  const wasCorrect = quality >= 3;

  let newEaseFactor = card.easeFactor;
  let newRepetitions = card.repetitions;
  let newInterval = card.interval;
  let newStatus = card.status;
  let newCorrectStreak = card.correctStreak;

  if (wasCorrect) {
    // Successful recall - update ease factor and advance interval
    newEaseFactor = calculateEaseFactor(card.easeFactor, quality);
    newRepetitions = card.repetitions + 1;
    newInterval = calculateInterval(newRepetitions, newEaseFactor, card.interval);
    newCorrectStreak = card.correctStreak + 1;

    // Update status based on interval
    if (newInterval > 21) {
      newStatus = 'graduated';
    } else if (newStatus === 'new' || newStatus === 'learning') {
      newStatus = 'review';
    }
  } else {
    // Failed recall - reset to learning phase
    newRepetitions = 0;
    newInterval = SM2_DEFAULTS.LAPSE_INTERVAL; // 1 day
    newCorrectStreak = 0;
    newStatus = 'learning';

    // Still update ease factor (will decrease)
    newEaseFactor = calculateEaseFactor(card.easeFactor, quality);
  }

  // Calculate next review date
  const nextReviewDate = new Date(now);
  nextReviewDate.setDate(nextReviewDate.getDate() + newInterval);

  return {
    ...card,
    easeFactor: newEaseFactor,
    interval: newInterval,
    repetitions: newRepetitions,
    nextReviewDate: nextReviewDate.toISOString(),
    status: newStatus,
    lastReviewDate: now.toISOString(),
    lastQuality: quality,
    totalReviews: card.totalReviews + 1,
    correctStreak: newCorrectStreak,
    updatedAt: now.toISOString(),
  };
}

/**
 * Check if a card is due for review
 */
export function isCardDue(card: CardState, referenceDate?: Date): boolean {
  const now = referenceDate || new Date();
  const nextReview = new Date(card.nextReviewDate);
  return nextReview <= now;
}

/**
 * Calculate how overdue a card is (in days)
 * Positive = overdue, Negative = not yet due
 */
export function getOverdueDays(card: CardState, referenceDate?: Date): number {
  const now = referenceDate || new Date();
  const nextReview = new Date(card.nextReviewDate);
  const diffMs = now.getTime() - nextReview.getTime();
  return Math.floor(diffMs / (1000 * 60 * 60 * 24));
}

/**
 * Estimate the interval that will result from a given rating
 * Useful for showing preview intervals on rating buttons
 */
export function previewInterval(card: CardState, quality: QualityRating): number {
  const wasCorrect = quality >= 3;

  if (!wasCorrect) {
    return SM2_DEFAULTS.LAPSE_INTERVAL; // 1 day
  }

  const newEaseFactor = calculateEaseFactor(card.easeFactor, quality);
  const newRepetitions = card.repetitions + 1;

  return calculateInterval(newRepetitions, newEaseFactor, card.interval);
}

/**
 * Format interval for display (e.g., "1d", "6d", "2w", "1m")
 */
export function formatInterval(days: number): string {
  if (days === 0) {
    return 'now';
  }

  if (days < 1) {
    const minutes = Math.round(days * 24 * 60);
    return `${minutes}m`;
  }

  if (days < 7) {
    return `${days}d`;
  }

  if (days < 30) {
    const weeks = Math.round(days / 7);
    return `${weeks}w`;
  }

  if (days < 365) {
    const months = Math.round(days / 30);
    return `${months}mo`;
  }

  const years = Math.round(days / 365 * 10) / 10;
  return `${years}y`;
}

/**
 * Get a description of the card's learning status
 */
export function getStatusDescription(card: CardState): string {
  switch (card.status) {
    case 'new':
      return 'New card - not yet studied';
    case 'learning':
      return 'Learning - needs more practice';
    case 'review':
      return `Review - next in ${formatInterval(card.interval)}`;
    case 'graduated':
      return 'Mastered - well learned';
    case 'suspended':
      return 'Suspended - paused from review';
    default:
      return 'Unknown status';
  }
}
