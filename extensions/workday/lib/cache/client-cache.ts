import Dexie, { Table } from 'dexie';
import { CACHE_TTL, isCacheExpired } from './cache-keys';

/**
 * Client-Side Cache Manager (Tier 2)
 *
 * Uses IndexedDB via Dexie for client-side caching with 7-day expiration.
 * Provides persistent storage across browser sessions.
 */

interface CachedItem {
  key: string;
  value: any;
  createdAt: number;
  expiresAt: number;
  operation: string;
  patternId: string;
  size: number;
}

/**
 * Dexie database for client-side caching
 */
class WorkWiseCacheDB extends Dexie {
  cache!: Table<CachedItem, string>;

  constructor() {
    super('WorkWiseCache');

    this.version(1).stores({
      cache: 'key, expiresAt, operation, patternId, createdAt',
    });
  }
}

// Initialize database instance
let db: WorkWiseCacheDB | null = null;

/**
 * Initialize IndexedDB connection
 * @returns Database instance
 */
function getDB(): WorkWiseCacheDB {
  if (!db) {
    db = new WorkWiseCacheDB();
  }
  return db;
}

/**
 * Get item from client cache
 * @param key - Cache key
 * @returns Cached value or null if not found/expired
 */
export async function getFromClientCache<T = any>(key: string): Promise<T | null> {
  try {
    const db = getDB();
    const item = await db.cache.get(key);

    if (!item) {
      return null;
    }

    // Check expiration
    if (isCacheExpired(item.expiresAt)) {
      // Remove expired item
      await db.cache.delete(key);
      return null;
    }

    return item.value as T;
  } catch (error) {
    console.error('[Client Cache] Get error:', error);
    return null;
  }
}

/**
 * Set item in client cache
 * @param key - Cache key
 * @param value - Value to cache
 * @param options - Cache options
 */
export async function setInClientCache(
  key: string,
  value: any,
  options: {
    operation: string;
    patternId: string;
    ttl?: number;
  }
): Promise<void> {
  try {
    const db = getDB();
    const ttl = options.ttl || CACHE_TTL.TIER2;

    const item: CachedItem = {
      key,
      value,
      createdAt: Date.now(),
      expiresAt: Date.now() + (ttl * 1000),
      operation: options.operation,
      patternId: options.patternId,
      size: JSON.stringify(value).length,
    };

    await db.cache.put(item);

    // Log cache write in development
    if (process.env.NODE_ENV === 'development') {
      console.log('[Client Cache] Set:', {
        key,
        operation: options.operation,
        patternId: options.patternId,
        size: `${(item.size / 1024).toFixed(2)} KB`,
      });
    }
  } catch (error) {
    console.error('[Client Cache] Set error:', error);
  }
}

/**
 * Delete item from client cache
 * @param key - Cache key
 */
export async function deleteFromClientCache(key: string): Promise<void> {
  try {
    const db = getDB();
    await db.cache.delete(key);
  } catch (error) {
    console.error('[Client Cache] Delete error:', error);
  }
}

/**
 * Clear all items for a specific pattern
 * @param patternId - Pattern ID
 */
export async function clearPatternCache(patternId: string): Promise<void> {
  try {
    const db = getDB();
    await db.cache.where('patternId').equals(patternId).delete();

    if (process.env.NODE_ENV === 'development') {
      console.log('[Client Cache] Cleared cache for pattern:', patternId);
    }
  } catch (error) {
    console.error('[Client Cache] Clear pattern error:', error);
  }
}

/**
 * Clear all items for a specific operation type
 * @param operation - Operation type
 */
export async function clearOperationCache(operation: string): Promise<void> {
  try {
    const db = getDB();
    await db.cache.where('operation').equals(operation).delete();

    if (process.env.NODE_ENV === 'development') {
      console.log('[Client Cache] Cleared cache for operation:', operation);
    }
  } catch (error) {
    console.error('[Client Cache] Clear operation error:', error);
  }
}

/**
 * Clear all expired items
 * @returns Number of items cleared
 */
export async function clearExpiredCache(): Promise<number> {
  try {
    const db = getDB();
    const now = Date.now();

    const expiredKeys = await db.cache
      .where('expiresAt')
      .below(now)
      .primaryKeys();

    if (expiredKeys.length > 0) {
      await db.cache.bulkDelete(expiredKeys);

      if (process.env.NODE_ENV === 'development') {
        console.log('[Client Cache] Cleared expired items:', expiredKeys.length);
      }
    }

    return expiredKeys.length;
  } catch (error) {
    console.error('[Client Cache] Clear expired error:', error);
    return 0;
  }
}

/**
 * Clear all cache items
 */
export async function clearAllCache(): Promise<void> {
  try {
    const db = getDB();
    await db.cache.clear();

    if (process.env.NODE_ENV === 'development') {
      console.log('[Client Cache] Cleared all cache');
    }
  } catch (error) {
    console.error('[Client Cache] Clear all error:', error);
  }
}

/**
 * Get cache statistics
 * @returns Cache statistics
 */
export async function getCacheStats(): Promise<{
  totalItems: number;
  totalSize: number;
  byOperation: Record<string, number>;
  oldestItem: number;
  newestItem: number;
}> {
  try {
    const db = getDB();
    const allItems = await db.cache.toArray();

    const stats = {
      totalItems: allItems.length,
      totalSize: 0,
      byOperation: {} as Record<string, number>,
      oldestItem: Date.now(),
      newestItem: 0,
    };

    for (const item of allItems) {
      stats.totalSize += item.size;
      stats.byOperation[item.operation] = (stats.byOperation[item.operation] || 0) + 1;

      if (item.createdAt < stats.oldestItem) {
        stats.oldestItem = item.createdAt;
      }
      if (item.createdAt > stats.newestItem) {
        stats.newestItem = item.createdAt;
      }
    }

    return stats;
  } catch (error) {
    console.error('[Client Cache] Stats error:', error);
    return {
      totalItems: 0,
      totalSize: 0,
      byOperation: {},
      oldestItem: Date.now(),
      newestItem: Date.now(),
    };
  }
}

/**
 * Check if item exists in cache (without retrieving it)
 * @param key - Cache key
 * @returns True if exists and not expired
 */
export async function existsInClientCache(key: string): Promise<boolean> {
  try {
    const db = getDB();
    const item = await db.cache.get(key);

    if (!item) {
      return false;
    }

    if (isCacheExpired(item.expiresAt)) {
      await db.cache.delete(key);
      return false;
    }

    return true;
  } catch (error) {
    console.error('[Client Cache] Exists check error:', error);
    return false;
  }
}

/**
 * Get multiple items from cache
 * @param keys - Array of cache keys
 * @returns Map of key to value (only non-expired items)
 */
export async function getBulkFromClientCache<T = any>(
  keys: string[]
): Promise<Map<string, T>> {
  try {
    const db = getDB();
    const items = await db.cache.bulkGet(keys);
    const result = new Map<string, T>();
    const now = Date.now();

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item && !isCacheExpired(item.expiresAt)) {
        result.set(keys[i], item.value as T);
      } else if (item && isCacheExpired(item.expiresAt)) {
        // Clean up expired item
        await db.cache.delete(keys[i]);
      }
    }

    return result;
  } catch (error) {
    console.error('[Client Cache] Bulk get error:', error);
    return new Map();
  }
}

/**
 * Initialize cache and perform cleanup
 * Should be called when the app starts
 */
export async function initializeClientCache(): Promise<void> {
  try {
    const db = getDB();

    // Test connection
    await db.cache.count();

    // Clear expired items
    await clearExpiredCache();

    if (process.env.NODE_ENV === 'development') {
      const stats = await getCacheStats();
      console.log('[Client Cache] Initialized:', {
        items: stats.totalItems,
        size: `${(stats.totalSize / 1024 / 1024).toFixed(2)} MB`,
        operations: Object.keys(stats.byOperation).join(', '),
      });
    }
  } catch (error) {
    console.error('[Client Cache] Initialization error:', error);
  }
}
