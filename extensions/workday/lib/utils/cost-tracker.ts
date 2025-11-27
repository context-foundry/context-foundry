/**
 * Cost Tracker Utilities
 *
 * Tracks OpenAI API usage and estimates costs for monitoring and budget management.
 * Logs token consumption, estimates costs, and provides aggregation utilities.
 */

export interface CostEstimate {
  operation: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  estimatedCost: number;
  timestamp: string;
  cacheHit: boolean;
  cacheSource?: 'tier1' | 'tier2' | 'tier3';
}

export interface CostSummary {
  totalCost: number;
  totalTokens: number;
  totalOperations: number;
  cacheHitRate: number;
  costByOperation: Record<string, number>;
  tokensByOperation: Record<string, number>;
  operationCounts: Record<string, number>;
}

/**
 * Pricing per 1M tokens (as of January 2025)
 * Update these values when OpenAI changes pricing
 */
const MODEL_PRICING: Record<
  string,
  { input: number; output: number }
> = {
  'gpt-4o': {
    input: 5.0, // $5.00 per 1M input tokens
    output: 15.0, // $15.00 per 1M output tokens
  },
  'gpt-4o-mini': {
    input: 0.15, // $0.15 per 1M input tokens
    output: 0.6, // $0.60 per 1M output tokens
  },
  'gpt-4-turbo': {
    input: 10.0, // $10.00 per 1M input tokens
    output: 30.0, // $30.00 per 1M output tokens
  },
  'dall-e-3': {
    input: 0, // DALL-E pricing is per-image, not per-token
    output: 0,
  },
};

/**
 * DALL-E 3 pricing per image
 */
const DALLE_PRICING: Record<string, number> = {
  'standard-1024x1024': 0.04, // $0.04 per image
  'standard-1024x1792': 0.08, // $0.08 per image
  'standard-1792x1024': 0.08, // $0.08 per image
  'hd-1024x1024': 0.08, // $0.08 per image
  'hd-1024x1792': 0.12, // $0.12 per image
  'hd-1792x1024': 0.12, // $0.12 per image
};

/**
 * Calculate cost estimate for token usage
 * @param model - Model name
 * @param inputTokens - Number of input tokens
 * @param outputTokens - Number of output tokens
 * @returns Estimated cost in USD
 */
export function calculateTokenCost(
  model: string,
  inputTokens: number,
  outputTokens: number
): number {
  const pricing = MODEL_PRICING[model];

  if (!pricing) {
    console.warn(`Unknown model pricing for: ${model}. Using gpt-4o-mini pricing as fallback.`);
    const fallbackPricing = MODEL_PRICING['gpt-4o-mini'];
    return (
      (inputTokens / 1_000_000) * fallbackPricing.input +
      (outputTokens / 1_000_000) * fallbackPricing.output
    );
  }

  const inputCost = (inputTokens / 1_000_000) * pricing.input;
  const outputCost = (outputTokens / 1_000_000) * pricing.output;

  return inputCost + outputCost;
}

/**
 * Calculate cost for DALL-E image generation
 * @param quality - Image quality (standard or hd)
 * @param size - Image size
 * @returns Estimated cost in USD
 */
export function calculateImageCost(
  quality: 'standard' | 'hd',
  size: '1024x1024' | '1024x1792' | '1792x1024'
): number {
  const key = `${quality}-${size}`;
  return DALLE_PRICING[key] || DALLE_PRICING['standard-1024x1024'];
}

/**
 * Create and log a cost estimate
 * @param params - Cost estimate parameters
 * @returns Cost estimate object
 */
export function logCostEstimate(params: {
  operation: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  cacheHit?: boolean;
  cacheSource?: 'tier1' | 'tier2' | 'tier3';
}): CostEstimate {
  const totalTokens = params.inputTokens + params.outputTokens;
  const estimatedCost = params.cacheHit
    ? 0
    : calculateTokenCost(params.model, params.inputTokens, params.outputTokens);

  const estimate: CostEstimate = {
    operation: params.operation,
    model: params.model,
    inputTokens: params.inputTokens,
    outputTokens: params.outputTokens,
    totalTokens,
    estimatedCost,
    timestamp: new Date().toISOString(),
    cacheHit: params.cacheHit || false,
    cacheSource: params.cacheSource,
  };

  // Log to console in development
  if (process.env.NODE_ENV === 'development') {
    console.log('[Cost Tracker]', {
      operation: estimate.operation,
      tokens: `${estimate.inputTokens} in / ${estimate.outputTokens} out / ${estimate.totalTokens} total`,
      cost: `$${estimate.estimatedCost.toFixed(6)}`,
      cacheHit: estimate.cacheHit,
      cacheSource: estimate.cacheSource || 'N/A',
    });
  }

  return estimate;
}

/**
 * Log DALL-E image generation cost
 * @param params - Image generation parameters
 * @returns Cost estimate object
 */
export function logImageCost(params: {
  operation: string;
  quality: 'standard' | 'hd';
  size: '1024x1024' | '1024x1792' | '1792x1024';
  cacheHit?: boolean;
  cacheSource?: 'tier1' | 'tier2' | 'tier3';
}): CostEstimate {
  const estimatedCost = params.cacheHit ? 0 : calculateImageCost(params.quality, params.size);

  const estimate: CostEstimate = {
    operation: params.operation,
    model: 'dall-e-3',
    inputTokens: 0,
    outputTokens: 0,
    totalTokens: 0,
    estimatedCost,
    timestamp: new Date().toISOString(),
    cacheHit: params.cacheHit || false,
    cacheSource: params.cacheSource,
  };

  // Log to console in development
  if (process.env.NODE_ENV === 'development') {
    console.log('[Cost Tracker - Image]', {
      operation: estimate.operation,
      quality: params.quality,
      size: params.size,
      cost: `$${estimate.estimatedCost.toFixed(4)}`,
      cacheHit: estimate.cacheHit,
      cacheSource: estimate.cacheSource || 'N/A',
    });
  }

  return estimate;
}

/**
 * Aggregate cost estimates into summary
 * @param estimates - Array of cost estimates
 * @returns Cost summary
 */
export function aggregateCosts(estimates: CostEstimate[]): CostSummary {
  const summary: CostSummary = {
    totalCost: 0,
    totalTokens: 0,
    totalOperations: estimates.length,
    cacheHitRate: 0,
    costByOperation: {},
    tokensByOperation: {},
    operationCounts: {},
  };

  let cacheHits = 0;

  for (const estimate of estimates) {
    // Aggregate totals
    summary.totalCost += estimate.estimatedCost;
    summary.totalTokens += estimate.totalTokens;

    // Track cache hits
    if (estimate.cacheHit) {
      cacheHits++;
    }

    // Aggregate by operation
    const op = estimate.operation;
    summary.costByOperation[op] = (summary.costByOperation[op] || 0) + estimate.estimatedCost;
    summary.tokensByOperation[op] = (summary.tokensByOperation[op] || 0) + estimate.totalTokens;
    summary.operationCounts[op] = (summary.operationCounts[op] || 0) + 1;
  }

  // Calculate cache hit rate
  summary.cacheHitRate = estimates.length > 0 ? (cacheHits / estimates.length) * 100 : 0;

  return summary;
}

/**
 * Format cost for display
 * @param cost - Cost in USD
 * @returns Formatted cost string
 */
export function formatCost(cost: number): string {
  if (cost < 0.01) {
    return `$${cost.toFixed(6)}`;
  }
  if (cost < 1) {
    return `$${cost.toFixed(4)}`;
  }
  return `$${cost.toFixed(2)}`;
}

/**
 * Format token count for display
 * @param tokens - Token count
 * @returns Formatted token string
 */
export function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(2)}M`;
  }
  if (tokens >= 1_000) {
    return `${(tokens / 1_000).toFixed(1)}K`;
  }
  return tokens.toString();
}

/**
 * Check if budget threshold is exceeded
 * @param currentCost - Current total cost
 * @param budgetLimit - Budget limit in USD
 * @returns Object with exceeded status and percentage
 */
export function checkBudgetThreshold(
  currentCost: number,
  budgetLimit: number
): { exceeded: boolean; percentage: number; warning: boolean } {
  const percentage = (currentCost / budgetLimit) * 100;

  return {
    exceeded: percentage >= 100,
    percentage,
    warning: percentage >= 80,
  };
}

/**
 * Estimate tokens for text (rough approximation)
 * @param text - Text to estimate
 * @returns Estimated token count
 */
export function estimateTokens(text: string): number {
  // Rough estimation: 1 token ≈ 4 characters for English text
  // This is a conservative estimate; actual tokenization may vary
  return Math.ceil(text.length / 4);
}
