/**
 * Configuration management for BAML + Anthropic integration.
 *
 * Loads environment variables and provides typed configuration access.
 */

import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Configuration interface for BAML + Anthropic integration.
 */
export interface Config {
  anthropicApiKey: string;
  bamlLogLevel: string;
  runIntegrationTests: boolean;
  logLevel: string;
}

/**
 * Load configuration from environment variables.
 *
 * @param envFile - Optional path to .env file
 * @returns Configuration object
 * @throws Error if required configuration is missing
 *
 * @example
 * ```typescript
 * const config = loadConfig();
 * console.log(`API Key: ${config.anthropicApiKey}`);
 * ```
 */
export function loadConfig(envFile?: string): Config {
  // Determine .env file location
  const envPath =
    envFile ||
    path.join(__dirname, '../../.env') ||
    path.join(__dirname, '../../../.env');

  // Load environment variables
  dotenv.config({ path: envPath });

  // Extract configuration
  const config: Config = {
    anthropicApiKey: process.env.ANTHROPIC_API_KEY || '',
    bamlLogLevel: process.env.BAML_LOG_LEVEL || 'INFO',
    runIntegrationTests:
      process.env.RUN_INTEGRATION_TESTS?.toLowerCase() === 'true',
    logLevel: process.env.LOG_LEVEL || 'INFO',
  };

  // Validate required fields
  validateConfig(config);

  return config;
}

/**
 * Validate configuration object.
 *
 * @param config - Configuration to validate
 * @throws Error if configuration is invalid
 */
function validateConfig(config: Config): void {
  // Validate API key
  if (!config.anthropicApiKey || config.anthropicApiKey.length < 10) {
    throw new Error(
      'Invalid or missing ANTHROPIC_API_KEY environment variable. ' +
        'Please set it in your .env file.'
    );
  }

  if (config.anthropicApiKey === 'your_api_key_here') {
    throw new Error(
      'ANTHROPIC_API_KEY is still set to the template value. ' +
        'Please replace it with your actual API key.'
    );
  }

  // Validate log levels
  const validLogLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
  const bamlLogLevelUpper = config.bamlLogLevel.toUpperCase();
  const logLevelUpper = config.logLevel.toUpperCase();

  if (!validLogLevels.includes(bamlLogLevelUpper)) {
    throw new Error(
      `Invalid BAML_LOG_LEVEL: ${config.bamlLogLevel}. ` +
        `Must be one of: ${validLogLevels.join(', ')}`
    );
  }

  if (!validLogLevels.includes(logLevelUpper)) {
    throw new Error(
      `Invalid LOG_LEVEL: ${config.logLevel}. ` +
        `Must be one of: ${validLogLevels.join(', ')}`
    );
  }

  // Normalize case
  config.bamlLogLevel = bamlLogLevelUpper;
  config.logLevel = logLevelUpper;
}

/**
 * Get configuration (convenience function).
 *
 * @returns Configuration object
 */
export function getConfig(): Config {
  return loadConfig();
}
