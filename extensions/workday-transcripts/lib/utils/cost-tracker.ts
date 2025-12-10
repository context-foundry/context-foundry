/**
 * Cost Tracker Utilities
 *
 * Tracks OpenAI API usage and estimates costs for monitoring and budget management.
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
  cacheSource?: 'static' | 'indexeddb';
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
 */
const MODEL_PRICING: Record<string, { input: number; output: number }> = {
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
};

/**
 * Calculate cost estimate for token usage
 */
export function calculateTokenCost(
  model: string,
  inputTokens: number,
  outputTokens: number
): number {
  const pricing = MODEL_PRICING[model];

  if (!pricing) {
    console.warn(
      `Unknown model pricing for: ${model}. Using gpt-4o-mini pricing as fallback.`
    );
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
 * Create and log a cost estimate
 */
export function logCostEstimate(params: {
  operation: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  cacheHit?: boolean;
  cacheSource?: 'static' | 'indexeddb';
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
 * Aggregate cost estimates into summary
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
    summary.totalCost += estimate.estimatedCost;
    summary.totalTokens += estimate.totalTokens;

    if (estimate.cacheHit) {
      cacheHits++;
    }

    const op = estimate.operation;
    summary.costByOperation[op] =
      (summary.costByOperation[op] || 0) + estimate.estimatedCost;
    summary.tokensByOperation[op] =
      (summary.tokensByOperation[op] || 0) + estimate.totalTokens;
    summary.operationCounts[op] = (summary.operationCounts[op] || 0) + 1;
  }

  summary.cacheHitRate =
    estimates.length > 0 ? (cacheHits / estimates.length) * 100 : 0;

  return summary;
}

/**
 * Format cost for display
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
 * Estimate tokens for text (rough approximation)
 */
export function estimateTokens(text: string): number {
  // Rough estimation: 1 token ≈ 4 characters for English text
  return Math.ceil(text.length / 4);
}
