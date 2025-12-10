import { z } from 'zod';
import { QualityRatingSchema } from './card';

/**
 * Result of a single card review
 */
export const CardReviewResultSchema = z.object({
  cardId: z.string().uuid(),
  quality: QualityRatingSchema,
  responseTimeMs: z.number().int().min(0),
  previousInterval: z.number().int().min(0),
  newInterval: z.number().int().min(0),
  previousEaseFactor: z.number(),
  newEaseFactor: z.number(),
  wasCorrect: z.boolean(), // quality >= 3
  timestamp: z.string().datetime(),
});

export type CardReviewResult = z.infer<typeof CardReviewResultSchema>;

/**
 * A complete review session
 */
export const ReviewSessionSchema = z.object({
  id: z.string().uuid(),
  startedAt: z.string().datetime(),
  completedAt: z.string().datetime().optional(),

  // Session statistics
  cardsReviewed: z.number().int().min(0),
  cardsCorrect: z.number().int().min(0), // Quality >= 3
  newCardsStudied: z.number().int().min(0),
  reviewCardsStudied: z.number().int().min(0),

  // Aggregate metrics
  averageQuality: z.number().min(0).max(5),
  averageResponseTimeMs: z.number().int().min(0),
  timeSpentSeconds: z.number().int().min(0),

  // Per-card results
  cardResults: z.array(CardReviewResultSchema),
});

export type ReviewSession = z.infer<typeof ReviewSessionSchema>;

/**
 * Daily review summary (for streak tracking)
 */
export const DailyReviewSummarySchema = z.object({
  date: z.string(), // YYYY-MM-DD format
  sessionsCompleted: z.number().int().min(0),
  totalCardsReviewed: z.number().int().min(0),
  totalCorrect: z.number().int().min(0),
  averageQuality: z.number().min(0).max(5),
  timeSpentMinutes: z.number().min(0),
  newCardsStudied: z.number().int().min(0),
});

export type DailyReviewSummary = z.infer<typeof DailyReviewSummarySchema>;

/**
 * Review queue configuration
 */
export const ReviewQueueConfigSchema = z.object({
  newCardsPerDay: z.number().int().min(0).default(20),
  maxReviewsPerDay: z.number().int().min(0).default(200),
  learnAheadMinutes: z.number().int().min(0).default(20),
  showOverdueFirst: z.boolean().default(true),
});

export type ReviewQueueConfig = z.infer<typeof ReviewQueueConfigSchema>;

/**
 * Default review queue configuration
 */
export const DEFAULT_REVIEW_CONFIG: ReviewQueueConfig = {
  newCardsPerDay: 20,
  maxReviewsPerDay: 200,
  learnAheadMinutes: 20,
  showOverdueFirst: true,
};

/**
 * Review queue state for current session
 */
export const ReviewQueueStateSchema = z.object({
  // Queue contents
  dueCards: z.array(z.string().uuid()), // Card IDs due for review
  newCards: z.array(z.string().uuid()), // New cards to introduce
  learningCards: z.array(z.string().uuid()), // Cards in learning phase

  // Progress tracking
  reviewedCount: z.number().int().min(0),
  correctCount: z.number().int().min(0),
  currentIndex: z.number().int().min(0),

  // Timestamps
  queueBuiltAt: z.string().datetime(),
  lastReviewAt: z.string().datetime().optional(),
});

export type ReviewQueueState = z.infer<typeof ReviewQueueStateSchema>;

/**
 * Create a new review session
 */
export function createReviewSession(): Omit<ReviewSession, 'completedAt'> {
  return {
    id: crypto.randomUUID(),
    startedAt: new Date().toISOString(),
    cardsReviewed: 0,
    cardsCorrect: 0,
    newCardsStudied: 0,
    reviewCardsStudied: 0,
    averageQuality: 0,
    averageResponseTimeMs: 0,
    timeSpentSeconds: 0,
    cardResults: [],
  };
}

/**
 * Calculate session statistics from card results
 */
export function calculateSessionStats(
  results: CardReviewResult[]
): Pick<
  ReviewSession,
  'cardsReviewed' | 'cardsCorrect' | 'averageQuality' | 'averageResponseTimeMs'
> {
  if (results.length === 0) {
    return {
      cardsReviewed: 0,
      cardsCorrect: 0,
      averageQuality: 0,
      averageResponseTimeMs: 0,
    };
  }

  const totalQuality = results.reduce((sum, r) => sum + r.quality, 0);
  const totalTime = results.reduce((sum, r) => sum + r.responseTimeMs, 0);
  const correctCount = results.filter((r) => r.wasCorrect).length;

  return {
    cardsReviewed: results.length,
    cardsCorrect: correctCount,
    averageQuality: totalQuality / results.length,
    averageResponseTimeMs: Math.round(totalTime / results.length),
  };
}
