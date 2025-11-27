/**
 * Vercel KV Cache Layer (Tier 3)
 *
 * Server-side shared cache for deduplication across users.
 * Provides 24-hour TTL for AI-generated content.
 *
 * This is an alias/re-export for server-cache.ts to match architecture naming.
 */

export * from './server-cache';
