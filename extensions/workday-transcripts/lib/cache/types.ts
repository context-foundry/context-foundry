/**
 * Cache type definitions for IndexedDB storage
 */

import { type FlashCard, type CardState } from '@/types/card';
import { type ReviewSession } from '@/types/review';
import { type UserProgress } from '@/types/progress';
import { type TranscriptMetadata } from '@/types/transcript';

/**
 * Cache entry metadata
 */
export interface CacheMetadata {
  key: string;
  createdAt: number;
  expiresAt: number;
  size: number;
}

/**
 * Cached flashcard data (content + state)
 */
export interface CachedCard extends CacheMetadata {
  card: FlashCard;
}

/**
 * Cached card state
 */
export interface CachedCardState extends CacheMetadata {
  state: CardState;
}

/**
 * Cached review session
 */
export interface CachedReviewSession extends CacheMetadata {
  session: ReviewSession;
}

/**
 * Cached user progress
 */
export interface CachedUserProgress extends CacheMetadata {
  progress: UserProgress;
}

/**
 * Cached transcript metadata
 */
export interface CachedTranscript extends CacheMetadata {
  transcript: TranscriptMetadata;
}

/**
 * Generic cache item
 */
export interface CachedItem<T = any> {
  key: string;
  value: T;
  createdAt: number;
  expiresAt: number;
  size: number;
}

/**
 * Database table names
 */
export const DB_TABLES = {
  CARDS: 'cards',
  CARD_STATES: 'cardStates',
  REVIEW_SESSIONS: 'reviewSessions',
  USER_PROGRESS: 'userProgress',
  TRANSCRIPTS: 'transcripts',
  CACHE: 'cache',
} as const;

/**
 * Cache TTL configurations (in milliseconds)
 */
export const CACHE_TTL = {
  // Cards never expire (static content)
  CARDS: Infinity,

  // Card states never expire (user data)
  CARD_STATES: Infinity,

  // Review sessions never expire (historical data)
  REVIEW_SESSIONS: Infinity,

  // Progress never expires (user data)
  USER_PROGRESS: Infinity,

  // Transcript metadata expires after 30 days
  TRANSCRIPTS: 30 * 24 * 60 * 60 * 1000,

  // General cache expires after 7 days
  CACHE: 7 * 24 * 60 * 60 * 1000,
} as const;

/**
 * Check if a cache item is expired
 */
export function isCacheExpired(expiresAt: number): boolean {
  if (expiresAt === Infinity) return false;
  return Date.now() > expiresAt;
}

/**
 * Calculate expiration timestamp
 */
export function calculateExpiration(ttl: number): number {
  if (ttl === Infinity) return Infinity;
  return Date.now() + ttl;
}
