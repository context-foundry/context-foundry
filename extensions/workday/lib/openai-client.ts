import OpenAI from 'openai';
import { validateAPIKey, withRetry, logError, parseAPIError } from '@/lib/utils/error-handler';
import { logCostEstimate, logImageCost } from '@/lib/utils/cost-tracker';

/**
 * OpenAI Client
 *
 * Centralized OpenAI API client with error handling, retry logic,
 * rate limiting, and cost estimation.
 */

// Validate API key at module load time
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
validateAPIKey(OPENAI_API_KEY);

// Initialize OpenAI client
const openai = new OpenAI({
  apiKey: OPENAI_API_KEY,
});

/**
 * Default model for chat completions
 */
export const DEFAULT_MODEL = 'gpt-4o-mini';

/**
 * Default model for image generation
 */
export const DEFAULT_IMAGE_MODEL = 'dall-e-3';

/**
 * Generate chat completion with retry logic and cost tracking
 * @param params - Chat completion parameters
 * @returns Chat completion response
 */
export async function generateChatCompletion(params: {
  messages: OpenAI.Chat.ChatCompletionMessageParam[];
  model?: string;
  temperature?: number;
  maxTokens?: number;
  responseFormat?: { type: 'json_object' } | { type: 'text' };
  operation?: string;
}): Promise<OpenAI.Chat.ChatCompletionMessage> {
  const model = params.model || DEFAULT_MODEL;
  const operation = params.operation || 'chat-completion';

  try {
    const completion = await withRetry(async () => {
      return await openai.chat.completions.create({
        model,
        messages: params.messages,
        temperature: params.temperature ?? 0.7,
        max_tokens: params.maxTokens,
        response_format: params.responseFormat,
      });
    });

    // Extract usage statistics
    const usage = completion.usage;
    if (usage) {
      logCostEstimate({
        operation,
        model,
        inputTokens: usage.prompt_tokens,
        outputTokens: usage.completion_tokens,
        cacheHit: false,
      });
    }

    const message = completion.choices[0]?.message;
    if (!message) {
      throw new Error('No message in completion response');
    }

    return message;
  } catch (error) {
    const apiError = parseAPIError(error);
    logError(apiError, { operation, model });
    throw apiError;
  }
}

/**
 * Generate structured JSON response with retry logic and cost tracking
 * @param params - Completion parameters
 * @returns Parsed JSON response
 */
export async function generateStructuredJSON<T = any>(params: {
  messages: OpenAI.Chat.ChatCompletionMessageParam[];
  model?: string;
  temperature?: number;
  maxTokens?: number;
  operation?: string;
}): Promise<T> {
  const message = await generateChatCompletion({
    ...params,
    responseFormat: { type: 'json_object' },
  });

  try {
    const content = message.content;
    if (!content) {
      throw new Error('No content in completion response');
    }

    return JSON.parse(content) as T;
  } catch (error) {
    console.error('Failed to parse JSON response:', error);
    throw new Error('Invalid JSON response from OpenAI API');
  }
}

/**
 * Generate image with DALL-E 3
 * @param params - Image generation parameters
 * @returns Image URL
 */
export async function generateImage(params: {
  prompt: string;
  size?: '1024x1024' | '1024x1792' | '1792x1024';
  quality?: 'standard' | 'hd';
  operation?: string;
}): Promise<string> {
  const size = params.size || '1024x1024';
  const quality = params.quality || 'standard';
  const operation = params.operation || 'image-generation';

  try {
    const response = await withRetry(async () => {
      return await openai.images.generate({
        model: DEFAULT_IMAGE_MODEL,
        prompt: params.prompt,
        size,
        quality,
        n: 1,
      });
    });

    // Log cost estimate
    logImageCost({
      operation,
      quality,
      size,
      cacheHit: false,
    });

    const imageUrl = response.data[0]?.url;
    if (!imageUrl) {
      throw new Error('No image URL in response');
    }

    return imageUrl;
  } catch (error) {
    const apiError = parseAPIError(error);
    logError(apiError, { operation, prompt: params.prompt });
    throw apiError;
  }
}

/**
 * Count tokens in text (approximate)
 * This is a rough estimate; actual tokenization may vary
 * @param text - Text to count tokens for
 * @returns Estimated token count
 */
export function estimateTokenCount(text: string): number {
  // Rough estimation: 1 token ≈ 4 characters for English text
  return Math.ceil(text.length / 4);
}

/**
 * Validate completion response
 * @param message - Chat completion message
 * @param expectedFields - Expected fields in JSON response
 * @returns True if valid
 */
export function validateCompletionResponse(
  message: OpenAI.Chat.ChatCompletionMessage,
  expectedFields: string[] = []
): boolean {
  if (!message.content) {
    return false;
  }

  if (expectedFields.length === 0) {
    return true;
  }

  try {
    const parsed = JSON.parse(message.content);
    return expectedFields.every((field) => field in parsed);
  } catch {
    return false;
  }
}

/**
 * Create system message
 * @param content - System message content
 * @returns System message
 */
export function createSystemMessage(content: string): OpenAI.Chat.ChatCompletionMessageParam {
  return {
    role: 'system',
    content,
  };
}

/**
 * Create user message
 * @param content - User message content
 * @returns User message
 */
export function createUserMessage(content: string): OpenAI.Chat.ChatCompletionMessageParam {
  return {
    role: 'user',
    content,
  };
}

/**
 * Rate limiter for API calls
 * Simple implementation to prevent hitting rate limits
 */
class RateLimiter {
  private queue: Array<() => Promise<any>> = [];
  private processing = false;
  private lastCallTime = 0;
  private minInterval: number;

  constructor(callsPerMinute: number = 60) {
    this.minInterval = 60000 / callsPerMinute; // Convert to ms per call
  }

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      this.queue.push(async () => {
        try {
          const result = await fn();
          resolve(result);
        } catch (error) {
          reject(error);
        }
      });

      if (!this.processing) {
        this.processQueue();
      }
    });
  }

  private async processQueue(): Promise<void> {
    if (this.queue.length === 0) {
      this.processing = false;
      return;
    }

    this.processing = true;
    const now = Date.now();
    const timeSinceLastCall = now - this.lastCallTime;

    if (timeSinceLastCall < this.minInterval) {
      await new Promise((resolve) => setTimeout(resolve, this.minInterval - timeSinceLastCall));
    }

    const fn = this.queue.shift();
    if (fn) {
      this.lastCallTime = Date.now();
      await fn();
    }

    this.processQueue();
  }
}

// Export rate limiter instance (60 calls per minute)
export const rateLimiter = new RateLimiter(60);

// Export OpenAI client for advanced usage
export { openai };
