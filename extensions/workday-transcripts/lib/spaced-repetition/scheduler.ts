/**
 * Review Scheduling Utilities
 *
 * Handles date calculations and scheduling for spaced repetition.
 */

import {
  addDays,
  addMinutes,
  format,
  startOfDay,
  isToday,
  isBefore,
  differenceInDays,
} from 'date-fns';
import { type CardState } from '@/types/card';

/**
 * Get the start of today (midnight)
 */
export function getTodayStart(): Date {
  return startOfDay(new Date());
}

/**
 * Calculate the next review date from a given interval
 */
export function calculateNextReviewDate(
  intervalDays: number,
  fromDate?: Date
): Date {
  const base = fromDate || new Date();
  return addDays(startOfDay(base), intervalDays);
}

/**
 * Calculate the next review date for learning cards (short intervals in minutes)
 */
export function calculateLearningReviewDate(
  intervalMinutes: number,
  fromDate?: Date
): Date {
  const base = fromDate || new Date();
  return addMinutes(base, intervalMinutes);
}

/**
 * Format a date for display
 */
export function formatReviewDate(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;

  if (isToday(d)) {
    return 'Today';
  }

  const daysUntil = differenceInDays(d, startOfDay(new Date()));

  if (daysUntil === 1) {
    return 'Tomorrow';
  }

  if (daysUntil < 7) {
    return format(d, 'EEEE'); // e.g., "Monday"
  }

  if (daysUntil < 30) {
    return format(d, 'MMM d'); // e.g., "Jan 15"
  }

  return format(d, 'MMM d, yyyy'); // e.g., "Jan 15, 2025"
}

/**
 * Check if a card is due for review today
 */
export function isDueToday(card: CardState): boolean {
  const nextReview = new Date(card.nextReviewDate);
  return isBefore(nextReview, addDays(getTodayStart(), 1));
}

/**
 * Check if a card is overdue (was due before today)
 */
export function isOverdue(card: CardState): boolean {
  const nextReview = new Date(card.nextReviewDate);
  return isBefore(nextReview, getTodayStart());
}

/**
 * Get days until card is due
 * Negative = overdue, 0 = due today, Positive = due in future
 */
export function getDaysUntilDue(card: CardState): number {
  const nextReview = startOfDay(new Date(card.nextReviewDate));
  const today = getTodayStart();
  return differenceInDays(nextReview, today);
}

/**
 * Sort cards by due date (most overdue first)
 */
export function sortByDueDate(cards: CardState[]): CardState[] {
  return [...cards].sort((a, b) => {
    const dateA = new Date(a.nextReviewDate).getTime();
    const dateB = new Date(b.nextReviewDate).getTime();
    return dateA - dateB;
  });
}

/**
 * Group cards by due status
 */
export function groupByDueStatus(cards: CardState[]): {
  overdue: CardState[];
  dueToday: CardState[];
  future: CardState[];
} {
  const overdue: CardState[] = [];
  const dueToday: CardState[] = [];
  const future: CardState[] = [];

  const today = getTodayStart();
  const tomorrow = addDays(today, 1);

  for (const card of cards) {
    const nextReview = new Date(card.nextReviewDate);

    if (isBefore(nextReview, today)) {
      overdue.push(card);
    } else if (isBefore(nextReview, tomorrow)) {
      dueToday.push(card);
    } else {
      future.push(card);
    }
  }

  return {
    overdue: sortByDueDate(overdue),
    dueToday: sortByDueDate(dueToday),
    future: sortByDueDate(future),
  };
}

/**
 * Calculate forecast of reviews for upcoming days
 */
export function calculateReviewForecast(
  cards: CardState[],
  daysAhead: number = 7
): Array<{ date: string; count: number }> {
  const forecast: Map<string, number> = new Map();
  const today = getTodayStart();

  // Initialize all days
  for (let i = 0; i < daysAhead; i++) {
    const date = format(addDays(today, i), 'yyyy-MM-dd');
    forecast.set(date, 0);
  }

  // Count cards due each day
  for (const card of cards) {
    const dueDate = startOfDay(new Date(card.nextReviewDate));
    const dateStr = format(dueDate, 'yyyy-MM-dd');

    // If overdue, count as today
    if (isBefore(dueDate, today)) {
      const todayStr = format(today, 'yyyy-MM-dd');
      forecast.set(todayStr, (forecast.get(todayStr) || 0) + 1);
    } else if (forecast.has(dateStr)) {
      forecast.set(dateStr, (forecast.get(dateStr) || 0) + 1);
    }
  }

  return Array.from(forecast.entries()).map(([date, count]) => ({
    date,
    count,
  }));
}

/**
 * Get today's date as YYYY-MM-DD string
 */
export function getTodayString(): string {
  return format(new Date(), 'yyyy-MM-dd');
}

/**
 * Parse a date string to Date object
 */
export function parseDate(dateStr: string): Date {
  return new Date(dateStr);
}
