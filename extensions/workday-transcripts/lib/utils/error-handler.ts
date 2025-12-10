/**
 * Error Handler Utilities
 *
 * Provides error handling utilities for API calls with retry logic,
 * exponential backoff, and user-friendly error messages.
 */

export interface APIError {
  message: string;
  code?: string;
  status?: number;
  retryable: boolean;
  userMessage: string;
}

export interface RetryConfig {
  maxAttempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxAttempts: 3,
  baseDelayMs: 1000,
  maxDelayMs: 10000,
  backoffMultiplier: 2,
};

/**
 * Parse error into standardized APIError format
 */
export function parseAPIError(error: unknown): APIError {
  // OpenAI SDK errors
  if (error && typeof error === 'object' && 'error' in error) {
    const openAIError = error as any;
    const errorMessage =
      openAIError.error?.message || openAIError.message || 'Unknown OpenAI error';
    const status = openAIError.status || openAIError.error?.status;
    const code = openAIError.error?.code || openAIError.code;

    return {
      message: errorMessage,
      code,
      status,
      retryable: isRetryableError(status, code),
      userMessage: getUserFriendlyMessage(status, code, errorMessage),
    };
  }

  // Standard Error objects
  if (error instanceof Error) {
    return {
      message: error.message,
      retryable: false,
      userMessage: 'An unexpected error occurred. Please try again.',
    };
  }

  // Unknown error types
  return {
    message: String(error),
    retryable: false,
    userMessage: 'An unexpected error occurred. Please try again.',
  };
}

/**
 * Determine if an error is retryable
 */
function isRetryableError(status?: number, code?: string): boolean {
  if (status === 429) return true;
  if (status && status >= 500) return true;
  if (code === 'ECONNRESET' || code === 'ETIMEDOUT' || code === 'ENOTFOUND') return true;
  if (code === 'rate_limit_exceeded' || code === 'server_error') return true;
  return false;
}

/**
 * Get user-friendly error message
 */
function getUserFriendlyMessage(
  status?: number,
  code?: string,
  originalMessage?: string
): string {
  if (status === 429 || code === 'rate_limit_exceeded') {
    return 'We are experiencing high demand. Please wait a moment and try again.';
  }

  if (status === 401 || status === 403) {
    return 'Authentication failed. Please check your API key configuration.';
  }

  if (status === 400) {
    return 'Invalid request. Please try again or contact support.';
  }

  if (status && status >= 500) {
    return 'The service is temporarily unavailable. We will retry automatically.';
  }

  if (code === 'ECONNRESET' || code === 'ETIMEDOUT') {
    return 'Network connection issue. Retrying...';
  }

  if (originalMessage && originalMessage.toLowerCase().includes('api key')) {
    return 'Invalid API key format. Please ensure your OPENAI_API_KEY environment variable is set correctly.';
  }

  return 'An error occurred while processing your request. Please try again.';
}

/**
 * Calculate delay for exponential backoff
 */
function calculateBackoffDelay(attempt: number, config: RetryConfig): number {
  const delay = config.baseDelayMs * Math.pow(config.backoffMultiplier, attempt);
  return Math.min(delay, config.maxDelayMs);
}

/**
 * Sleep for specified duration
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Execute function with retry logic and exponential backoff
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  config: Partial<RetryConfig> = {}
): Promise<T> {
  const retryConfig = { ...DEFAULT_RETRY_CONFIG, ...config };
  let lastError: APIError | null = null;

  for (let attempt = 0; attempt < retryConfig.maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = parseAPIError(error);

      if (!lastError.retryable) {
        throw lastError;
      }

      if (attempt === retryConfig.maxAttempts - 1) {
        throw lastError;
      }

      const delay = calculateBackoffDelay(attempt, retryConfig);
      console.log(
        `Attempt ${attempt + 1}/${retryConfig.maxAttempts} failed: ${lastError.message}. Retrying in ${delay}ms...`
      );
      await sleep(delay);
    }
  }

  throw lastError;
}

/**
 * Log error with context
 */
export function logError(error: APIError, context: Record<string, any> = {}): void {
  console.error('[API Error]', {
    message: error.message,
    code: error.code,
    status: error.status,
    retryable: error.retryable,
    userMessage: error.userMessage,
    timestamp: new Date().toISOString(),
    ...context,
  });
}

/**
 * Validate API key format
 */
export function validateAPIKey(
  apiKey: string | undefined,
  prefix: string = 'sk-'
): void {
  if (!apiKey) {
    throw new Error(
      `API key is not set. Please set the OPENAI_API_KEY environment variable.`
    );
  }

  if (!apiKey.startsWith(prefix)) {
    throw new Error(
      `Invalid API key format. OpenAI API keys must start with '${prefix}'.`
    );
  }

  if (apiKey.length < 20) {
    throw new Error(`API key appears to be invalid (too short).`);
  }
}
