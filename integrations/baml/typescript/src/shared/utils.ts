/**
 * Utility functions for BAML + Anthropic integration.
 *
 * Includes logging setup, retry logic, and error classes.
 */

/**
 * Retry an async function with exponential backoff.
 *
 * @param func - Async function to retry
 * @param maxRetries - Maximum number of retry attempts
 * @param initialDelay - Initial delay in milliseconds before first retry
 * @param backoffFactor - Multiplier for delay after each retry
 * @returns Result from successful function call
 * @throws Last exception if all retries fail
 *
 * @example
 * ```typescript
 * const result = await retryWithBackoff(
 *   async () => await apiCall(),
 *   3,
 *   1000,
 *   2
 * );
 * ```
 */
export async function retryWithBackoff<T>(
  func: () => Promise<T>,
  maxRetries: number = 3,
  initialDelay: number = 1000,
  backoffFactor: number = 2
): Promise<T> {
  let delay = initialDelay;
  let lastError: Error | undefined;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await func();
    } catch (error) {
      lastError = error as Error;
      console.warn(
        `Attempt ${attempt + 1}/${maxRetries} failed: ${lastError.message}. ` +
          `Retrying in ${delay}ms...`
      );

      if (attempt < maxRetries - 1) {
        await sleep(delay);
        delay *= backoffFactor;
      }
    }
  }

  // All retries failed
  console.error(`All ${maxRetries} attempts failed`);
  throw lastError || new Error('Retry failed with unknown error');
}

/**
 * Sleep for a specified number of milliseconds.
 *
 * @param ms - Milliseconds to sleep
 * @returns Promise that resolves after the delay
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Decorator for automatic retry with exponential backoff.
 *
 * @param maxRetries - Maximum number of retry attempts
 * @param initialDelay - Initial delay in milliseconds
 * @param backoffFactor - Multiplier for delay after each retry
 * @returns Decorated method with retry logic
 *
 * @example
 * ```typescript
 * class MyService {
 *   @asyncRetry(3, 1000, 2)
 *   async myApiCall() {
 *     // API call that may fail
 *   }
 * }
 * ```
 */
export function asyncRetry(
  maxRetries: number = 3,
  initialDelay: number = 1000,
  backoffFactor: number = 2
) {
  return function (
    target: any,
    propertyKey: string,
    descriptor: PropertyDescriptor
  ) {
    const originalMethod = descriptor.value;

    descriptor.value = async function (...args: any[]) {
      return retryWithBackoff(
        () => originalMethod.apply(this, args),
        maxRetries,
        initialDelay,
        backoffFactor
      );
    };

    return descriptor;
  };
}

/**
 * Custom error class for document processing errors.
 */
export class DocumentProcessingError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DocumentProcessingError';
    Object.setPrototypeOf(this, DocumentProcessingError.prototype);
  }
}

/**
 * Custom error class for data analysis errors.
 */
export class DataAnalysisError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DataAnalysisError';
    Object.setPrototypeOf(this, DataAnalysisError.prototype);
  }
}

/**
 * Custom error class for skill execution errors.
 */
export class SkillExecutionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'SkillExecutionError';
    Object.setPrototypeOf(this, SkillExecutionError.prototype);
  }
}

/**
 * Custom error class for configuration errors.
 */
export class ConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigurationError';
    Object.setPrototypeOf(this, ConfigurationError.prototype);
  }
}

/**
 * Simple logger with level support.
 */
export class Logger {
  private level: string;

  constructor(level: string = 'INFO') {
    this.level = level.toUpperCase();
  }

  debug(message: string, ...args: any[]): void {
    if (this.shouldLog('DEBUG')) {
      console.debug(`[DEBUG] ${message}`, ...args);
    }
  }

  info(message: string, ...args: any[]): void {
    if (this.shouldLog('INFO')) {
      console.info(`[INFO] ${message}`, ...args);
    }
  }

  warn(message: string, ...args: any[]): void {
    if (this.shouldLog('WARNING')) {
      console.warn(`[WARNING] ${message}`, ...args);
    }
  }

  error(message: string, ...args: any[]): void {
    if (this.shouldLog('ERROR')) {
      console.error(`[ERROR] ${message}`, ...args);
    }
  }

  private shouldLog(messageLevel: string): boolean {
    const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
    const currentLevelIndex = levels.indexOf(this.level);
    const messageLevelIndex = levels.indexOf(messageLevel);
    return messageLevelIndex >= currentLevelIndex;
  }
}

/**
 * Create a logger instance.
 *
 * @param level - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
 * @returns Logger instance
 */
export function createLogger(level: string = 'INFO'): Logger {
  return new Logger(level);
}
