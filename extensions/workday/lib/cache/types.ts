/**
 * Cache Type Definitions
 *
 * Shared type definitions for the three-tier caching strategy.
 */

export interface CachedItem {
  key: string;
  value: any;
  createdAt: number;
  expiresAt: number;
  operation: string;
  patternId: string;
  size: number;
}

export interface CacheMetadata {
  source: 'indexeddb' | 'vercel-kv' | 'openai' | 'static';
  cached: boolean;
  timestamp: number;
  ttl?: number;
}

export interface CacheStats {
  hits: number;
  misses: number;
  hitRate: number;
  totalSize: number;
  itemCount: number;
}

export type CacheTier = 'tier1' | 'tier2' | 'tier3';

export const CACHE_TTL = {
  TIER1_STATIC: Infinity, // Build-time static generation
  TIER2_INDEXEDDB: 30 * 24 * 60 * 60 * 1000, // 30 days in milliseconds
  TIER3_VERCEL_KV: 24 * 60 * 60, // 24 hours in seconds
} as const;
