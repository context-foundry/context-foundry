import { z } from 'zod';
import { WorkdayCategorySchema } from './card';

/**
 * Category-level progress tracking
 */
export const CategoryProgressSchema = z.object({
  cardsTotal: z.number().int().min(0),
  cardsLearned: z.number().int().min(0), // Graduated cards
  cardsInProgress: z.number().int().min(0), // Learning/review status
  cardsNew: z.number().int().min(0), // Never seen
  averageEaseFactor: z.number().min(1.3).max(2.5),
  totalReviews: z.number().int().min(0),
  retentionRate: z.number().min(0).max(100), // % correct
});

export type CategoryProgress = z.infer<typeof CategoryProgressSchema>;

/**
 * User progress tracking
 */
export const UserProgressSchema = z.object({
  userId: z.string().default('default'),

  // Overall card statistics
  totalCards: z.number().int().min(0).default(0),
  totalReviews: z.number().int().min(0).default(0),
  cardsLearned: z.number().int().min(0).default(0), // Graduated
  cardsInProgress: z.number().int().min(0).default(0),
  cardsNew: z.number().int().min(0).default(0),
  cardsDue: z.number().int().min(0).default(0),

  // Streak tracking
  currentStreak: z.number().int().min(0).default(0), // Consecutive days studied
  longestStreak: z.number().int().min(0).default(0),
  lastStudyDate: z.string().datetime().optional(),

  // Category breakdown
  categoryProgress: z.record(WorkdayCategorySchema, CategoryProgressSchema).default({}),

  // Retention metrics
  retentionRate: z.number().min(0).max(100).default(0), // Overall % correct
  averageEaseFactor: z.number().min(1.3).max(2.5).default(2.5),

  // Session statistics
  totalSessions: z.number().int().min(0).default(0),
  totalTimeMinutes: z.number().min(0).default(0),
  averageSessionMinutes: z.number().min(0).default(0),

  // Timestamps
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export type UserProgress = z.infer<typeof UserProgressSchema>;

/**
 * Progress snapshot for a specific date (for historical tracking)
 */
export const ProgressSnapshotSchema = z.object({
  date: z.string(), // YYYY-MM-DD
  cardsLearned: z.number().int().min(0),
  cardsDue: z.number().int().min(0),
  cardsReviewed: z.number().int().min(0),
  retentionRate: z.number().min(0).max(100),
  streakDay: z.number().int().min(0),
});

export type ProgressSnapshot = z.infer<typeof ProgressSnapshotSchema>;

/**
 * Forecast for upcoming reviews
 */
export const ReviewForecastSchema = z.object({
  date: z.string(), // YYYY-MM-DD
  reviewCount: z.number().int().min(0),
  newCount: z.number().int().min(0),
});

export type ReviewForecast = z.infer<typeof ReviewForecastSchema>;

/**
 * Create initial user progress
 */
export function createUserProgress(): UserProgress {
  const now = new Date().toISOString();
  return {
    userId: 'default',
    totalCards: 0,
    totalReviews: 0,
    cardsLearned: 0,
    cardsInProgress: 0,
    cardsNew: 0,
    cardsDue: 0,
    currentStreak: 0,
    longestStreak: 0,
    categoryProgress: {},
    retentionRate: 0,
    averageEaseFactor: 2.5,
    totalSessions: 0,
    totalTimeMinutes: 0,
    averageSessionMinutes: 0,
    createdAt: now,
    updatedAt: now,
  };
}

/**
 * Create initial category progress
 */
export function createCategoryProgress(): CategoryProgress {
  return {
    cardsTotal: 0,
    cardsLearned: 0,
    cardsInProgress: 0,
    cardsNew: 0,
    averageEaseFactor: 2.5,
    totalReviews: 0,
    retentionRate: 0,
  };
}

/**
 * Calculate streak based on daily reviews
 * @param dailyReviews Array of dates (YYYY-MM-DD) when user reviewed
 * @param today Current date (YYYY-MM-DD)
 * @returns Current streak count
 */
export function calculateStreak(dailyReviews: string[], today: string): number {
  if (dailyReviews.length === 0) return 0;

  const sortedDates = [...dailyReviews].sort().reverse();
  const todayDate = new Date(today);

  // Check if user reviewed today or yesterday
  const mostRecent = sortedDates[0];
  const daysSinceLast = Math.floor(
    (todayDate.getTime() - new Date(mostRecent).getTime()) / (1000 * 60 * 60 * 24)
  );

  if (daysSinceLast > 1) return 0; // Streak broken

  let streak = 0;
  let currentDate = daysSinceLast === 0 ? todayDate : new Date(today);
  currentDate.setDate(currentDate.getDate() - daysSinceLast);

  const dateSet = new Set(sortedDates);

  while (true) {
    const dateStr = currentDate.toISOString().split('T')[0];
    if (!dateSet.has(dateStr)) break;
    streak++;
    currentDate.setDate(currentDate.getDate() - 1);
  }

  return streak;
}

/**
 * Calculate retention rate from review history
 * @param correct Number of correct reviews
 * @param total Total reviews
 * @returns Retention percentage (0-100)
 */
export function calculateRetentionRate(correct: number, total: number): number {
  if (total === 0) return 0;
  return Math.round((correct / total) * 100);
}
