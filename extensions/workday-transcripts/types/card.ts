import { z } from 'zod';

/**
 * Quality ratings per SM-2 algorithm (0-5 scale)
 * - 0: Complete blackout - no recall at all
 * - 1: Incorrect - but recognized answer when shown
 * - 2: Incorrect - answer seemed easy once seen
 * - 3: Correct - but with serious difficulty
 * - 4: Correct - after some hesitation
 * - 5: Perfect - instant, confident recall
 */
export const QualityRatingSchema = z.number().int().min(0).max(5);
export type QualityRating = z.infer<typeof QualityRatingSchema>;

/**
 * Simplified 4-button rating (maps to SM-2 scale)
 * - again: 0 (complete failure, reset to 1 day)
 * - hard: 2 (struggled, shorter interval)
 * - good: 4 (recalled with effort, normal interval)
 * - easy: 5 (perfect recall, longer interval)
 */
export const SimpleRatingSchema = z.enum(['again', 'hard', 'good', 'easy']);
export type SimpleRating = z.infer<typeof SimpleRatingSchema>;

/**
 * Map simplified rating to SM-2 quality rating
 */
export const RATING_TO_QUALITY: Record<SimpleRating, QualityRating> = {
  again: 0,
  hard: 2,
  good: 4,
  easy: 5,
};

/**
 * Workday content categories
 */
export const WorkdayCategorySchema = z.enum([
  'HCM',
  'Recruiting',
  'Learning',
  'Analytics',
  'General',
]);
export type WorkdayCategory = z.infer<typeof WorkdayCategorySchema>;

/**
 * Types of concepts that can be extracted from transcripts
 */
export const ConceptTypeSchema = z.enum([
  'definition', // "What is X?"
  'procedure', // "How do you X?"
  'fact', // "Where can you find X?"
  'comparison', // "What is the difference between X and Y?"
]);
export type ConceptType = z.infer<typeof ConceptTypeSchema>;

/**
 * Card difficulty levels
 */
export const DifficultySchema = z.enum(['easy', 'medium', 'hard']);
export type Difficulty = z.infer<typeof DifficultySchema>;

/**
 * Flashcard content (static, generated at build time)
 */
export const FlashCardSchema = z.object({
  id: z.string().uuid(),
  transcriptId: z.string(),
  question: z.string(),
  answer: z.string(),
  options: z.array(z.string()).optional(), // For multiple choice
  category: WorkdayCategorySchema,
  conceptType: ConceptTypeSchema,
  difficulty: DifficultySchema,
  createdAt: z.string().datetime(),
});

export type FlashCard = z.infer<typeof FlashCardSchema>;

/**
 * Card learning status
 */
export const CardStatusSchema = z.enum([
  'new', // Never reviewed
  'learning', // In initial learning phase (recently failed)
  'review', // In regular review cycle
  'graduated', // Mastered (interval > 21 days)
  'suspended', // Manually paused
]);
export type CardStatus = z.infer<typeof CardStatusSchema>;

/**
 * Card state with SM-2 scheduling fields
 * This is stored in IndexedDB and updated with each review
 */
export const CardStateSchema = z.object({
  // Card identity
  cardId: z.string().uuid(),

  // SM-2 Algorithm Fields
  easeFactor: z.number().min(1.3).default(2.5),
  interval: z.number().int().min(0).default(0), // Days until next review
  repetitions: z.number().int().min(0).default(0), // Successful reviews in a row

  // Scheduling
  nextReviewDate: z.string().datetime(),

  // Learning state
  status: CardStatusSchema.default('new'),

  // Review history
  lastReviewDate: z.string().datetime().optional(),
  lastQuality: QualityRatingSchema.optional(),
  totalReviews: z.number().int().default(0),
  correctStreak: z.number().int().default(0), // Reviews with quality >= 3

  // Timestamps
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export type CardState = z.infer<typeof CardStateSchema>;

/**
 * Combined card data (content + state) for display
 */
export const CardWithStateSchema = FlashCardSchema.merge(
  CardStateSchema.omit({ cardId: true })
);
export type CardWithState = z.infer<typeof CardWithStateSchema>;

/**
 * Create a new card state with default values
 */
export function createCardState(cardId: string): CardState {
  const now = new Date().toISOString();
  return {
    cardId,
    easeFactor: 2.5,
    interval: 0,
    repetitions: 0,
    nextReviewDate: now, // Due immediately
    status: 'new',
    totalReviews: 0,
    correctStreak: 0,
    createdAt: now,
    updatedAt: now,
  };
}

/**
 * Default values for SM-2 algorithm
 */
export const SM2_DEFAULTS = {
  INITIAL_EASE_FACTOR: 2.5,
  MIN_EASE_FACTOR: 1.3,
  MAX_EASE_FACTOR: 2.5,
  LEARNING_INTERVALS: [1, 10], // Minutes for learning steps
  GRADUATING_INTERVAL: 1, // Days
  EASY_BONUS: 1.3,
  HARD_MULTIPLIER: 1.2,
  LAPSE_INTERVAL: 1, // Days after failing
} as const;
