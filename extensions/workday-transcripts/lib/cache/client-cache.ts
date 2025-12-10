/**
 * Client-Side Cache Manager using IndexedDB via Dexie
 *
 * Provides persistent storage for:
 * - Flashcards (static content)
 * - Card states (SM-2 scheduling data)
 * - Review sessions (history)
 * - User progress (stats and streaks)
 */

import Dexie, { type Table } from 'dexie';
import { type FlashCard, type CardState, createCardState } from '@/types/card';
import { type ReviewSession, type DailyReviewSummary } from '@/types/review';
import { type UserProgress, createUserProgress } from '@/types/progress';
import { type TranscriptMetadata } from '@/types/transcript';
import { type CachedItem, DB_TABLES, CACHE_TTL, isCacheExpired, calculateExpiration } from './types';

/**
 * Dexie database schema for Workday Learn
 */
class WorkdayLearnDB extends Dexie {
  // Table declarations for TypeScript
  cards!: Table<FlashCard, string>;
  cardStates!: Table<CardState, string>;
  reviewSessions!: Table<ReviewSession, string>;
  userProgress!: Table<UserProgress, string>;
  transcripts!: Table<TranscriptMetadata, string>;
  dailySummaries!: Table<DailyReviewSummary, string>;
  cache!: Table<CachedItem, string>;

  constructor() {
    super('WorkdayLearnDB');

    // Define schema with indexes
    this.version(1).stores({
      // FlashCards: indexed by id, transcriptId, category
      cards: 'id, transcriptId, category, difficulty, createdAt',

      // CardStates: indexed by cardId, status, nextReviewDate
      cardStates: 'cardId, status, nextReviewDate, updatedAt',

      // ReviewSessions: indexed by id, startedAt
      reviewSessions: 'id, startedAt, completedAt',

      // UserProgress: single record per user
      userProgress: 'userId',

      // TranscriptMetadata: indexed by id, category
      transcripts: 'id, category, date',

      // DailyReviewSummary: indexed by date
      dailySummaries: 'date',

      // General cache: key-value store
      cache: 'key, expiresAt',
    });
  }
}

// Singleton database instance
let db: WorkdayLearnDB | null = null;

/**
 * Get the database instance (lazy initialization)
 */
export function getDB(): WorkdayLearnDB {
  if (!db) {
    db = new WorkdayLearnDB();
  }
  return db;
}

/**
 * Initialize the database and perform cleanup
 */
export async function initializeDatabase(): Promise<void> {
  try {
    const database = getDB();
    await database.open();

    // Clean up expired cache items
    await cleanupExpiredCache();

    console.log('[DB] Database initialized successfully');
  } catch (error) {
    console.error('[DB] Failed to initialize database:', error);
    throw error;
  }
}

// ============================================================================
// Card Operations
// ============================================================================

/**
 * Save a flashcard to the database
 */
export async function saveCard(card: FlashCard): Promise<void> {
  await getDB().cards.put(card);
}

/**
 * Save multiple flashcards
 */
export async function saveCards(cards: FlashCard[]): Promise<void> {
  await getDB().cards.bulkPut(cards);
}

/**
 * Get a flashcard by ID
 */
export async function getCard(id: string): Promise<FlashCard | undefined> {
  return getDB().cards.get(id);
}

/**
 * Get all flashcards
 */
export async function getAllCards(): Promise<FlashCard[]> {
  return getDB().cards.toArray();
}

/**
 * Get flashcards by transcript ID
 */
export async function getCardsByTranscript(transcriptId: string): Promise<FlashCard[]> {
  return getDB().cards.where('transcriptId').equals(transcriptId).toArray();
}

/**
 * Get flashcards by category
 */
export async function getCardsByCategory(category: string): Promise<FlashCard[]> {
  return getDB().cards.where('category').equals(category).toArray();
}

// ============================================================================
// Card State Operations
// ============================================================================

/**
 * Get or create card state for a card
 */
export async function getOrCreateCardState(cardId: string): Promise<CardState> {
  const existing = await getDB().cardStates.get(cardId);
  if (existing) return existing;

  const newState = createCardState(cardId);
  await getDB().cardStates.put(newState);
  return newState;
}

/**
 * Save card state
 */
export async function saveCardState(state: CardState): Promise<void> {
  await getDB().cardStates.put(state);
}

/**
 * Get all card states
 */
export async function getAllCardStates(): Promise<CardState[]> {
  return getDB().cardStates.toArray();
}

/**
 * Get cards due for review
 */
export async function getDueCardStates(referenceDate?: Date): Promise<CardState[]> {
  const now = referenceDate || new Date();
  return getDB().cardStates
    .where('nextReviewDate')
    .belowOrEqual(now.toISOString())
    .and((state) => state.status !== 'suspended')
    .toArray();
}

/**
 * Get card states by status
 */
export async function getCardStatesByStatus(status: CardState['status']): Promise<CardState[]> {
  return getDB().cardStates.where('status').equals(status).toArray();
}

/**
 * Get new cards (never reviewed)
 */
export async function getNewCardStates(): Promise<CardState[]> {
  return getDB().cardStates.where('status').equals('new').toArray();
}

// ============================================================================
// Review Session Operations
// ============================================================================

/**
 * Save a review session
 */
export async function saveReviewSession(session: ReviewSession): Promise<void> {
  await getDB().reviewSessions.put(session);
}

/**
 * Get a review session by ID
 */
export async function getReviewSession(id: string): Promise<ReviewSession | undefined> {
  return getDB().reviewSessions.get(id);
}

/**
 * Get all review sessions
 */
export async function getAllReviewSessions(): Promise<ReviewSession[]> {
  return getDB().reviewSessions.orderBy('startedAt').reverse().toArray();
}

/**
 * Get recent review sessions
 */
export async function getRecentSessions(limit: number = 10): Promise<ReviewSession[]> {
  return getDB().reviewSessions
    .orderBy('startedAt')
    .reverse()
    .limit(limit)
    .toArray();
}

// ============================================================================
// Daily Summary Operations
// ============================================================================

/**
 * Save daily review summary
 */
export async function saveDailySummary(summary: DailyReviewSummary): Promise<void> {
  await getDB().dailySummaries.put(summary);
}

/**
 * Get daily summary
 */
export async function getDailySummary(date: string): Promise<DailyReviewSummary | undefined> {
  return getDB().dailySummaries.get(date);
}

/**
 * Get daily summaries for a date range
 */
export async function getDailySummaries(
  startDate: string,
  endDate: string
): Promise<DailyReviewSummary[]> {
  return getDB().dailySummaries
    .where('date')
    .between(startDate, endDate, true, true)
    .toArray();
}

// ============================================================================
// User Progress Operations
// ============================================================================

/**
 * Get or create user progress
 */
export async function getOrCreateUserProgress(userId: string = 'default'): Promise<UserProgress> {
  const existing = await getDB().userProgress.get(userId);
  if (existing) return existing;

  const newProgress = createUserProgress();
  await getDB().userProgress.put(newProgress);
  return newProgress;
}

/**
 * Save user progress
 */
export async function saveUserProgress(progress: UserProgress): Promise<void> {
  await getDB().userProgress.put(progress);
}

// ============================================================================
// Transcript Operations
// ============================================================================

/**
 * Save transcript metadata
 */
export async function saveTranscript(transcript: TranscriptMetadata): Promise<void> {
  await getDB().transcripts.put(transcript);
}

/**
 * Save multiple transcripts
 */
export async function saveTranscripts(transcripts: TranscriptMetadata[]): Promise<void> {
  await getDB().transcripts.bulkPut(transcripts);
}

/**
 * Get all transcripts
 */
export async function getAllTranscripts(): Promise<TranscriptMetadata[]> {
  return getDB().transcripts.toArray();
}

/**
 * Get transcripts by category
 */
export async function getTranscriptsByCategory(category: string): Promise<TranscriptMetadata[]> {
  return getDB().transcripts.where('category').equals(category).toArray();
}

// ============================================================================
// General Cache Operations
// ============================================================================

/**
 * Get item from cache
 */
export async function getCacheItem<T>(key: string): Promise<T | null> {
  const item = await getDB().cache.get(key);

  if (!item) return null;

  if (isCacheExpired(item.expiresAt)) {
    await getDB().cache.delete(key);
    return null;
  }

  return item.value as T;
}

/**
 * Set item in cache
 */
export async function setCacheItem<T>(
  key: string,
  value: T,
  ttl: number = CACHE_TTL.CACHE
): Promise<void> {
  const item: CachedItem<T> = {
    key,
    value,
    createdAt: Date.now(),
    expiresAt: calculateExpiration(ttl),
    size: JSON.stringify(value).length,
  };

  await getDB().cache.put(item);
}

/**
 * Delete item from cache
 */
export async function deleteCacheItem(key: string): Promise<void> {
  await getDB().cache.delete(key);
}

/**
 * Clean up expired cache items
 */
export async function cleanupExpiredCache(): Promise<number> {
  const now = Date.now();
  const expired = await getDB().cache
    .where('expiresAt')
    .below(now)
    .primaryKeys();

  if (expired.length > 0) {
    await getDB().cache.bulkDelete(expired);
    console.log(`[DB] Cleaned up ${expired.length} expired cache items`);
  }

  return expired.length;
}

/**
 * Clear all data (for testing/reset)
 */
export async function clearAllData(): Promise<void> {
  const database = getDB();
  await database.cards.clear();
  await database.cardStates.clear();
  await database.reviewSessions.clear();
  await database.userProgress.clear();
  await database.transcripts.clear();
  await database.dailySummaries.clear();
  await database.cache.clear();
  console.log('[DB] All data cleared');
}

/**
 * Get database statistics
 */
export async function getDatabaseStats(): Promise<{
  cardCount: number;
  cardStateCount: number;
  sessionCount: number;
  transcriptCount: number;
  cacheSize: number;
}> {
  const database = getDB();

  const [cardCount, cardStateCount, sessionCount, transcriptCount, cacheItems] =
    await Promise.all([
      database.cards.count(),
      database.cardStates.count(),
      database.reviewSessions.count(),
      database.transcripts.count(),
      database.cache.toArray(),
    ]);

  const cacheSize = cacheItems.reduce((sum, item) => sum + item.size, 0);

  return {
    cardCount,
    cardStateCount,
    sessionCount,
    transcriptCount,
    cacheSize,
  };
}
