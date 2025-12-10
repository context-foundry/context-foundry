/**
 * OpenAI Client
 *
 * Wrapper for OpenAI API calls with error handling and cost tracking.
 */

import OpenAI from 'openai';

// Initialize OpenAI client
let openaiClient: OpenAI | null = null;

/**
 * Get or create OpenAI client
 */
export function getOpenAIClient(): OpenAI {
  if (!openaiClient) {
    const apiKey = process.env.OPENAI_API_KEY;

    if (!apiKey) {
      throw new Error('OPENAI_API_KEY environment variable is not set');
    }

    openaiClient = new OpenAI({ apiKey });
  }

  return openaiClient;
}

/**
 * Default model configuration
 */
export const DEFAULT_MODEL = process.env.OPENAI_MODEL || 'gpt-4o-mini';
export const DEFAULT_MAX_TOKENS = parseInt(process.env.OPENAI_MAX_TOKENS || '2000', 10);

/**
 * Cost per 1000 tokens (approximate, as of 2024)
 */
export const TOKEN_COSTS: Record<string, { input: number; output: number }> = {
  'gpt-4o-mini': { input: 0.00015, output: 0.0006 },
  'gpt-4o': { input: 0.005, output: 0.015 },
  'gpt-4-turbo': { input: 0.01, output: 0.03 },
  'gpt-3.5-turbo': { input: 0.0005, output: 0.0015 },
};

/**
 * Generate a chat completion
 */
export async function generateCompletion(
  systemPrompt: string,
  userPrompt: string,
  options: {
    model?: string;
    maxTokens?: number;
    temperature?: number;
  } = {}
): Promise<{
  content: string;
  usage: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
    estimatedCost: number;
  };
}> {
  const client = getOpenAIClient();
  const model = options.model || DEFAULT_MODEL;
  const maxTokens = options.maxTokens || DEFAULT_MAX_TOKENS;
  const temperature = options.temperature ?? 0.7;

  const response = await client.chat.completions.create({
    model,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    max_tokens: maxTokens,
    temperature,
  });

  const content = response.choices[0]?.message?.content || '';
  const usage = response.usage;

  // Calculate cost
  const costs = TOKEN_COSTS[model] || TOKEN_COSTS['gpt-4o-mini'];
  const promptCost = ((usage?.prompt_tokens || 0) / 1000) * costs.input;
  const completionCost = ((usage?.completion_tokens || 0) / 1000) * costs.output;

  return {
    content,
    usage: {
      promptTokens: usage?.prompt_tokens || 0,
      completionTokens: usage?.completion_tokens || 0,
      totalTokens: usage?.total_tokens || 0,
      estimatedCost: promptCost + completionCost,
    },
  };
}

/**
 * Generate JSON completion (with retry on parse failure)
 */
export async function generateJsonCompletion<T>(
  systemPrompt: string,
  userPrompt: string,
  parseFunction: (response: string) => T | null,
  options: {
    model?: string;
    maxTokens?: number;
    maxRetries?: number;
  } = {}
): Promise<{
  data: T | null;
  usage: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
    estimatedCost: number;
  };
}> {
  const maxRetries = options.maxRetries || 2;
  let lastError: Error | null = null;
  let totalUsage = {
    promptTokens: 0,
    completionTokens: 0,
    totalTokens: 0,
    estimatedCost: 0,
  };

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const result = await generateCompletion(systemPrompt, userPrompt, {
        model: options.model,
        maxTokens: options.maxTokens,
        temperature: attempt === 0 ? 0.7 : 0.5, // Lower temperature on retry
      });

      // Track usage
      totalUsage.promptTokens += result.usage.promptTokens;
      totalUsage.completionTokens += result.usage.completionTokens;
      totalUsage.totalTokens += result.usage.totalTokens;
      totalUsage.estimatedCost += result.usage.estimatedCost;

      // Try to parse
      const parsed = parseFunction(result.content);

      if (parsed !== null) {
        return { data: parsed, usage: totalUsage };
      }

      lastError = new Error('Failed to parse response');
    } catch (error) {
      lastError = error as Error;
      console.error(`Attempt ${attempt + 1} failed:`, error);
    }
  }

  console.error('All attempts failed:', lastError);
  return { data: null, usage: totalUsage };
}

/**
 * Track API usage for cost monitoring
 */
export interface UsageRecord {
  timestamp: string;
  operation: string;
  model: string;
  promptTokens: number;
  completionTokens: number;
  estimatedCost: number;
}

let usageHistory: UsageRecord[] = [];

/**
 * Record API usage
 */
export function recordUsage(record: Omit<UsageRecord, 'timestamp'>): void {
  usageHistory.push({
    ...record,
    timestamp: new Date().toISOString(),
  });

  // Keep only last 1000 records
  if (usageHistory.length > 1000) {
    usageHistory = usageHistory.slice(-1000);
  }
}

/**
 * Get usage summary
 */
export function getUsageSummary(): {
  totalCalls: number;
  totalTokens: number;
  totalCost: number;
  byOperation: Record<string, { calls: number; tokens: number; cost: number }>;
} {
  const summary = {
    totalCalls: usageHistory.length,
    totalTokens: 0,
    totalCost: 0,
    byOperation: {} as Record<string, { calls: number; tokens: number; cost: number }>,
  };

  for (const record of usageHistory) {
    summary.totalTokens += record.promptTokens + record.completionTokens;
    summary.totalCost += record.estimatedCost;

    if (!summary.byOperation[record.operation]) {
      summary.byOperation[record.operation] = { calls: 0, tokens: 0, cost: 0 };
    }

    summary.byOperation[record.operation].calls++;
    summary.byOperation[record.operation].tokens +=
      record.promptTokens + record.completionTokens;
    summary.byOperation[record.operation].cost += record.estimatedCost;
  }

  return summary;
}
