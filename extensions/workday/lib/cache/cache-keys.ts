import crypto from 'crypto';

/**
 * Cache Key Generation Utilities
 *
 * Generates consistent SHA256-based cache keys for the three-tier caching system.
 * Keys are deterministic to ensure cache hits across requests.
 */

export type CacheOperation = 'quiz' | 'scenario' | 'fill-blank' | 'image' | 'hint' | 'validation';

/**
 * Generate SHA256 hash for cache key
 * @param input - String to hash
 * @returns SHA256 hash as hex string
 */
function generateSHA256(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

/**
 * Generate cache key for pattern-based content
 * @param patternId - Pattern ID
 * @param operation - Operation type
 * @param variant - Optional variant (e.g., 'simple', 'adaptive')
 * @returns Cache key
 */
export function generateCacheKey(
  patternId: string,
  operation: CacheOperation,
  variant?: string
): string {
  const components = [patternId, operation];

  if (variant) {
    components.push(variant);
  }

  const inputString = components.join(':');
  const hash = generateSHA256(inputString);

  // Include readable prefix for debugging
  return `workwise:${operation}:${patternId.substring(0, 20)}:${hash.substring(0, 16)}`;
}

/**
 * Generate cache key for quiz content
 * @param patternId - Pattern ID
 * @param options - Quiz generation options
 * @returns Cache key
 */
export function generateQuizCacheKey(
  patternId: string,
  options?: { adaptive?: boolean; difficulty?: string }
): string {
  const variant = options?.adaptive
    ? `adaptive-${options.difficulty || 'default'}`
    : 'standard';

  return generateCacheKey(patternId, 'quiz', variant);
}

/**
 * Generate cache key for scenario content
 * @param patternId - Pattern ID
 * @param options - Scenario generation options
 * @returns Cache key
 */
export function generateScenarioCacheKey(
  patternId: string,
  options?: { simple?: boolean }
): string {
  const variant = options?.simple ? 'simple' : 'standard';
  return generateCacheKey(patternId, 'scenario', variant);
}

/**
 * Generate cache key for fill-blank exercise
 * @param patternId - Pattern ID
 * @returns Cache key
 */
export function generateFillBlankCacheKey(patternId: string): string {
  return generateCacheKey(patternId, 'fill-blank');
}

/**
 * Generate cache key for image content
 * @param patternId - Pattern ID
 * @param imageType - Type of image
 * @returns Cache key
 */
export function generateImageCacheKey(
  patternId: string,
  imageType: 'scenario' | 'pattern' | 'achievement'
): string {
  return generateCacheKey(patternId, 'image', imageType);
}

/**
 * Generate cache key for hint content
 * @param patternId - Pattern ID
 * @param context - Hint context (hashed for uniqueness)
 * @returns Cache key
 */
export function generateHintCacheKey(patternId: string, context: string): string {
  const contextHash = generateSHA256(context).substring(0, 8);
  return generateCacheKey(patternId, 'hint', contextHash);
}

/**
 * Generate cache key for validation results
 * @param contentHash - Hash of content being validated
 * @param validationType - Type of validation
 * @returns Cache key
 */
export function generateValidationCacheKey(
  contentHash: string,
  validationType: 'quiz' | 'scenario' | 'fill-blank'
): string {
  return `workwise:validation:${validationType}:${contentHash.substring(0, 16)}`;
}

/**
 * Parse cache key to extract components
 * @param cacheKey - Cache key to parse
 * @returns Parsed components or null if invalid
 */
export function parseCacheKey(cacheKey: string): {
  namespace: string;
  operation: string;
  patternId: string;
  hash: string;
} | null {
  const parts = cacheKey.split(':');

  if (parts.length < 4 || parts[0] !== 'workwise') {
    return null;
  }

  return {
    namespace: parts[0],
    operation: parts[1],
    patternId: parts[2],
    hash: parts[3],
  };
}

/**
 * Generate hash of content for validation caching
 * @param content - Content to hash (object will be stringified)
 * @returns Content hash
 */
export function generateContentHash(content: any): string {
  const contentString = typeof content === 'string'
    ? content
    : JSON.stringify(content);

  return generateSHA256(contentString);
}

/**
 * Generate cache key with TTL metadata
 * @param baseKey - Base cache key
 * @param ttlSeconds - Time to live in seconds
 * @returns Key with TTL metadata
 */
export function generateKeyWithTTL(baseKey: string, ttlSeconds: number): {
  key: string;
  expiresAt: number;
} {
  return {
    key: baseKey,
    expiresAt: Date.now() + (ttlSeconds * 1000),
  };
}

/**
 * Check if cached item is expired
 * @param expiresAt - Expiration timestamp
 * @returns True if expired
 */
export function isCacheExpired(expiresAt: number): boolean {
  return Date.now() > expiresAt;
}

/**
 * Cache TTL configurations (in seconds)
 */
export const CACHE_TTL = {
  // Tier 1: Build-time (static) - never expires
  TIER1: Infinity,

  // Tier 2: Client-side IndexedDB - 7 days
  TIER2: 7 * 24 * 60 * 60,

  // Tier 3: Server-side KV - 30 days
  TIER3: 30 * 24 * 60 * 60,

  // Short-lived caches
  HINT: 60 * 60, // 1 hour
  VALIDATION: 24 * 60 * 60, // 1 day
} as const;

/**
 * Cache namespace prefixes for different tiers
 */
export const CACHE_NAMESPACES = {
  TIER1: 'workwise:tier1',
  TIER2: 'workwise:tier2',
  TIER3: 'workwise:tier3',
  TEMP: 'workwise:temp',
} as const;

/**
 * Generate cache metadata for storage
 * @param params - Metadata parameters
 * @returns Cache metadata object
 */
export function generateCacheMetadata(params: {
  key: string;
  tier: 'tier1' | 'tier2' | 'tier3';
  operation: CacheOperation;
  patternId: string;
  size?: number;
}): {
  key: string;
  tier: string;
  operation: string;
  patternId: string;
  createdAt: number;
  expiresAt: number;
  size: number;
} {
  const ttl = params.tier === 'tier1'
    ? CACHE_TTL.TIER1
    : params.tier === 'tier2'
    ? CACHE_TTL.TIER2
    : CACHE_TTL.TIER3;

  return {
    key: params.key,
    tier: params.tier,
    operation: params.operation,
    patternId: params.patternId,
    createdAt: Date.now(),
    expiresAt: ttl === Infinity ? Infinity : Date.now() + (ttl * 1000),
    size: params.size || 0,
  };
}
