import { kv } from '@vercel/kv';
import { CACHE_TTL } from './cache-keys';

/**
 * Server-Side Cache Manager (Tier 3)
 *
 * Uses Vercel KV (Redis) for server-side caching with 30-day expiration.
 * Provides shared cache across all users and serverless functions.
 */

/**
 * Get item from server cache
 * @param key - Cache key
 * @returns Cached value or null if not found
 */
export async function getFromServerCache<T = any>(key: string): Promise<T | null> {
  try {
    const value = await kv.get<T>(key);

    if (process.env.NODE_ENV === 'development' && value !== null) {
      console.log('[Server Cache] Hit:', key);
    }

    return value;
  } catch (error) {
    console.error('[Server Cache] Get error:', error);
    return null;
  }
}

/**
 * Set item in server cache
 * @param key - Cache key
 * @param value - Value to cache
 * @param options - Cache options
 */
export async function setInServerCache(
  key: string,
  value: any,
  options?: {
    ttl?: number; // Time to live in seconds
    nx?: boolean; // Only set if key doesn't exist
    xx?: boolean; // Only set if key exists
  }
): Promise<void> {
  try {
    const ttl = options?.ttl || CACHE_TTL.TIER3;

    // Set with expiration
    if (options?.nx) {
      // Set only if not exists
      await kv.set(key, value, { ex: ttl, nx: true });
    } else if (options?.xx) {
      // Set only if exists
      await kv.set(key, value, { ex: ttl, xx: true });
    } else {
      // Normal set
      await kv.set(key, value, { ex: ttl });
    }

    if (process.env.NODE_ENV === 'development') {
      console.log('[Server Cache] Set:', {
        key,
        ttl: `${ttl}s (${Math.round(ttl / 86400)} days)`,
        size: `${(JSON.stringify(value).length / 1024).toFixed(2)} KB`,
      });
    }
  } catch (error) {
    console.error('[Server Cache] Set error:', error);
  }
}

/**
 * Delete item from server cache
 * @param key - Cache key
 */
export async function deleteFromServerCache(key: string): Promise<void> {
  try {
    await kv.del(key);

    if (process.env.NODE_ENV === 'development') {
      console.log('[Server Cache] Deleted:', key);
    }
  } catch (error) {
    console.error('[Server Cache] Delete error:', error);
  }
}

/**
 * Delete multiple items from server cache
 * @param keys - Array of cache keys
 */
export async function deleteBulkFromServerCache(keys: string[]): Promise<void> {
  try {
    if (keys.length === 0) return;

    await kv.del(...keys);

    if (process.env.NODE_ENV === 'development') {
      console.log('[Server Cache] Deleted bulk:', keys.length);
    }
  } catch (error) {
    console.error('[Server Cache] Bulk delete error:', error);
  }
}

/**
 * Check if item exists in cache
 * @param key - Cache key
 * @returns True if exists
 */
export async function existsInServerCache(key: string): Promise<boolean> {
  try {
    const exists = await kv.exists(key);
    return exists === 1;
  } catch (error) {
    console.error('[Server Cache] Exists check error:', error);
    return false;
  }
}

/**
 * Get multiple items from cache
 * @param keys - Array of cache keys
 * @returns Map of key to value
 */
export async function getBulkFromServerCache<T = any>(
  keys: string[]
): Promise<Map<string, T>> {
  try {
    if (keys.length === 0) {
      return new Map();
    }

    const values = await kv.mget<T[]>(...keys);
    const result = new Map<string, T>();

    for (let i = 0; i < keys.length; i++) {
      const value = values[i];
      if (value !== null && value !== undefined) {
        result.set(keys[i], value);
      }
    }

    return result;
  } catch (error) {
    console.error('[Server Cache] Bulk get error:', error);
    return new Map();
  }
}

/**
 * Set multiple items in cache
 * @param items - Map of key to value
 * @param ttl - Time to live in seconds
 */
export async function setBulkInServerCache(
  items: Map<string, any>,
  ttl?: number
): Promise<void> {
  try {
    const promises: Promise<void>[] = [];

    for (const [key, value] of items) {
      promises.push(setInServerCache(key, value, { ttl }));
    }

    await Promise.all(promises);
  } catch (error) {
    console.error('[Server Cache] Bulk set error:', error);
  }
}

/**
 * Clear all items matching a pattern
 * @param pattern - Key pattern (e.g., 'workwise:quiz:*')
 */
export async function clearServerCacheByPattern(pattern: string): Promise<number> {
  try {
    // Get all keys matching pattern
    const keys = await kv.keys(pattern);

    if (keys.length === 0) {
      return 0;
    }

    // Delete all matching keys
    await kv.del(...keys);

    if (process.env.NODE_ENV === 'development') {
      console.log('[Server Cache] Cleared pattern:', { pattern, count: keys.length });
    }

    return keys.length;
  } catch (error) {
    console.error('[Server Cache] Clear pattern error:', error);
    return 0;
  }
}

/**
 * Increment a counter in cache
 * @param key - Cache key
 * @param increment - Amount to increment (default 1)
 * @returns New value
 */
export async function incrementInServerCache(key: string, increment: number = 1): Promise<number> {
  try {
    return await kv.incrby(key, increment);
  } catch (error) {
    console.error('[Server Cache] Increment error:', error);
    return 0;
  }
}

/**
 * Get time to live for a key
 * @param key - Cache key
 * @returns TTL in seconds, or -1 if key doesn't exist, -2 if no expiration
 */
export async function getServerCacheTTL(key: string): Promise<number> {
  try {
    return await kv.ttl(key);
  } catch (error) {
    console.error('[Server Cache] TTL error:', error);
    return -1;
  }
}

/**
 * Get or set pattern (get from cache, or generate and cache if not found)
 * @param key - Cache key
 * @param generator - Async function to generate value if not cached
 * @param ttl - Time to live in seconds
 * @returns Cached or generated value
 */
export async function getOrSetServerCache<T>(
  key: string,
  generator: () => Promise<T>,
  ttl?: number
): Promise<{ value: T; cached: boolean }> {
  try {
    // Try to get from cache first
    const cached = await getFromServerCache<T>(key);

    if (cached !== null) {
      return { value: cached, cached: true };
    }

    // Generate new value
    const value = await generator();

    // Cache the generated value
    await setInServerCache(key, value, { ttl });

    return { value, cached: false };
  } catch (error) {
    console.error('[Server Cache] Get-or-set error:', error);
    // If caching fails, still return generated value
    const value = await generator();
    return { value, cached: false };
  }
}

/**
 * Get cache statistics for monitoring
 * @returns Cache statistics
 */
export async function getServerCacheStats(): Promise<{
  totalKeys: number;
  keysByPrefix: Record<string, number>;
}> {
  try {
    // Get all keys
    const allKeys = await kv.keys('workwise:*');

    const stats = {
      totalKeys: allKeys.length,
      keysByPrefix: {} as Record<string, number>,
    };

    // Group by prefix
    for (const key of allKeys) {
      const parts = key.split(':');
      if (parts.length >= 2) {
        const prefix = parts[1]; // 'quiz', 'scenario', etc.
        stats.keysByPrefix[prefix] = (stats.keysByPrefix[prefix] || 0) + 1;
      }
    }

    return stats;
  } catch (error) {
    console.error('[Server Cache] Stats error:', error);
    return {
      totalKeys: 0,
      keysByPrefix: {},
    };
  }
}

/**
 * Warm up cache with commonly accessed patterns
 * @param patternIds - Pattern IDs to warm up
 * @param operations - Operations to warm up
 */
export async function warmUpServerCache(
  patternIds: string[],
  operations: string[]
): Promise<void> {
  try {
    const keys: string[] = [];

    for (const patternId of patternIds) {
      for (const operation of operations) {
        keys.push(`workwise:${operation}:${patternId}`);
      }
    }

    const exists = await Promise.all(keys.map((key) => existsInServerCache(key)));
    const missing = keys.filter((_, i) => !exists[i]);

    if (process.env.NODE_ENV === 'development') {
      console.log('[Server Cache] Warm-up check:', {
        total: keys.length,
        cached: keys.length - missing.length,
        missing: missing.length,
      });
    }
  } catch (error) {
    console.error('[Server Cache] Warm-up error:', error);
  }
}
