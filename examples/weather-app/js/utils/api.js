/**
 * HTTP API Utilities
 * Provides robust HTTP client functionality with error handling, retries, and caching
 */

import { APP_CONFIG, ERROR_MESSAGES, FEATURES, PERFORMANCE } from '../constants/config.js';

/**
 * Custom error class for API-related errors
 */
export class APIError extends Error {
  constructor(message, status = 0, response = null) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.response = response;
    this.timestamp = new Date().toISOString();
  }
}

/**
 * Rate limiter to prevent API abuse
 */
class RateLimiter {
  constructor() {
    this.requests = [];
    this.maxRequests = APP_CONFIG.REQUESTS.RETRY_ATTEMPTS;
    this.timeWindow = 60000; // 1 minute
  }

  /**
   * Check if request can be made
   * @returns {boolean} - Whether request is allowed
   */
  canMakeRequest() {
    const now = Date.now();
    // Remove old requests outside time window
    this.requests = this.requests.filter(time => now - time < this.timeWindow);
    
    return this.requests.length < this.maxRequests;
  }

  /**
   * Record a new request
   */
  recordRequest() {
    this.requests.push(Date.now());
  }

  /**
   * Get time until next request is allowed
   * @returns {number} - Milliseconds until next request
   */
  getRetryAfter() {
    if (this.requests.length === 0) return 0;
    
    const oldestRequest = Math.min(...this.requests);
    const retryAfter = this.timeWindow - (Date.now() - oldestRequest);
    
    return Math.max(0, retryAfter);
  }
}

// Global rate limiter instance
const rateLimiter = new RateLimiter();

/**
 * Sleep utility for delays
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise<void>}
 */
export const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Check if user is online
 * @returns {boolean} - Online status
 */
export const isOnline = () => navigator.onLine;

/**
 * Log performance metrics
 * @param {string} operation - Operation name
 * @param {number} duration - Duration in milliseconds
 * @param {Object} metadata - Additional metadata
 */
const logPerformance = (operation, duration, metadata = {}) => {
  if (!PERFORMANCE.ENABLE_MONITORING) return;
  
  console.log(`[Performance] ${operation}: ${duration}ms`, metadata);
};

/**
 * Log API calls for debugging
 * @param {string} method - HTTP method
 * @param {string} url - Request URL
 * @param {Object} options - Request options
 */
const logAPICall = (method, url, options = {}) => {
  if (!PERFORMANCE.LOG_API_CALLS) return;
  
  console.log(`[API Call] ${method.toUpperCase()} ${url}`, {
    headers: options.headers,
    body: options.body
  });
};

/**
 * Enhanced fetch with error handling, retries, and timeout
 * @param {string} url - Request URL
 * @param {Object} options - Fetch options
 * @returns {Promise<Response>} - Response object
 */
export const fetchWithRetry = async (url, options = {}) => {
  const startTime = Date.now();
  const {
    timeout = APP_CONFIG.REQUESTS.TIMEOUT,
    retries = APP_CONFIG.REQUESTS.RETRY_ATTEMPTS,
    retryDelay = APP_CONFIG.REQUESTS.RETRY_DELAY,
    backoff = APP_CONFIG.REQUESTS.RETRY_BACKOFF,
    ...fetchOptions
  } = options;

  // Check if online
  if (!isOnline()) {
    throw new APIError(ERROR_MESSAGES.NETWORK.OFFLINE, 0);
  }

  // Check rate limiting
  if (!rateLimiter.canMakeRequest()) {
    const retryAfter = rateLimiter.getRetryAfter();
    throw new APIError(
      `${ERROR_MESSAGES.NETWORK.RATE_LIMIT} Try again in ${Math.ceil(retryAfter / 1000)} seconds.`,
      429
    );
  }

  logAPICall(fetchOptions.method || 'GET', url, fetchOptions);

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      // Record request for rate limiting
      rateLimiter.recordRequest();

      // Create abort controller for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      // Make request
      const response = await fetch(url, {
        ...fetchOptions,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...fetchOptions.headers
        }
      });

      // Clear timeout
      clearTimeout(timeoutId);

      // Check if response is ok
      if (!response.ok) {
        throw new APIError(
          getErrorMessage(response.status),
          response.status,
          response
        );
      }

      // Log successful request
      const duration = Date.now() - startTime;
      logPerformance('API Request', duration, { 
        url, 
        status: response.status,
        attempt: attempt + 1
      });

      return response;

    } catch (error) {
      // Handle abort errors (timeout)
      if (error.name === 'AbortError') {
        error = new APIError(ERROR_MESSAGES.NETWORK.TIMEOUT, 0);
      }

      // Handle network errors
      if (!error.status) {
        error = new APIError(ERROR_MESSAGES.NETWORK.GENERIC, 0);
      }

      // If this is the last attempt, throw the error
      if (attempt === retries) {
        if (PERFORMANCE.LOG_ERRORS) {
          console.error(`[API Error] Failed after ${attempt + 1} attempts:`, error);
        }
        throw error;
      }

      // Wait before retrying with exponential backoff
      const delay = retryDelay * Math.pow(backoff, attempt);
      if (FEATURES.DEBUG_MODE) {
        console.log(`[API Retry] Attempt ${attempt + 1} failed, retrying in ${delay}ms`);
      }
      await sleep(delay);
    }
  }
};

/**
 * Get appropriate error message based on status code
 * @param {number} status - HTTP status code
 * @returns {string} - Error message
 */
const getErrorMessage = (status) => {
  switch (status) {
    case 401:
      return ERROR_MESSAGES.NETWORK.INVALID_KEY;
    case 404:
      return ERROR_MESSAGES.NETWORK.NOT_FOUND;
    case 429:
      return ERROR_MESSAGES.NETWORK.RATE_LIMIT;
    case 500:
    case 502:
    case 503:
    case 504:
      return ERROR_MESSAGES.NETWORK.SERVER_ERROR;
    default:
      return ERROR_MESSAGES.NETWORK.GENERIC;
  }
};

/**
 * Make GET request with caching support
 * @param {string} url - Request URL
 * @param {Object} options - Request options
 * @returns {Promise<any>} - Parsed JSON response
 */
export const get = async (url, options = {}) => {
  const response = await fetchWithRetry(url, {
    method: 'GET',
    ...options
  });

  try {
    const data = await response.json();
    return data;
  } catch (error) {
    throw new APIError(ERROR_MESSAGES.DATA.PARSE_ERROR, response.status);
  }
};

/**
 * Make POST request
 * @param {string} url - Request URL
 * @param {Object} data - Request body data
 * @param {Object} options - Request options
 * @returns {Promise<any>} - Parsed JSON response
 */
export const post = async (url, data = null, options = {}) => {
  const response = await fetchWithRetry(url, {
    method: 'POST',
    body: data ? JSON.stringify(data) : null,
    ...options
  });

  try {
    const responseData = await response.json();
    return responseData;
  } catch (error) {
    throw new APIError(ERROR_MESSAGES.DATA.PARSE_ERROR, response.status);
  }
};

/**
 * Build URL with query parameters
 * @param {string} baseUrl - Base URL
 * @param {Object} params - Query parameters
 * @returns {string} - Complete URL with parameters
 */
export const buildURL = (baseUrl, params = {}) => {
  if (!params || Object.keys(params).length === 0) {
    return baseUrl;
  }

  const searchParams = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      searchParams.append(key, String(value));
    }
  });

  const queryString = searchParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

/**
 * Validate URL format
 * @param {string} url - URL to validate
 * @returns {boolean} - Whether URL is valid
 */
export const isValidURL = (url) => {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
};

/**
 * Simple cache implementation for API responses
 */
export class APICache {
  constructor(maxSize = APP_CONFIG.CACHE.MAX_CACHE_SIZE) {
    this.cache = new Map();
    this.maxSize = maxSize;
  }

  /**
   * Generate cache key from URL and params
   * @param {string} url - Request URL
   * @param {Object} params - Request parameters
   * @returns {string} - Cache key
   */
  generateKey(url, params = {}) {
    const sortedParams = Object.keys(params)
      .sort()
      .reduce((result, key) => {
        result[key] = params[key];
        return result;
      }, {});
    
    return `${url}:${JSON.stringify(sortedParams)}`;
  }

  /**
   * Get item from cache
   * @param {string} key - Cache key
   * @returns {any|null} - Cached data or null if not found/expired
   */
  get(key) {
    const item = this.cache.get(key);
    
    if (!item) {
      return null;
    }

    // Check if item has expired
    if (Date.now() > item.expires) {
      this.cache.delete(key);
      return null;
    }

    // Move to end (LRU)
    this.cache.delete(key);
    this.cache.set(key, item);

    if (PERFORMANCE.LOG_CACHE_HITS) {
      console.log(`[Cache Hit] ${key}`);
    }

    return item.data;
  }

  /**
   * Set item in cache
   * @param {string} key - Cache key
   * @param {any} data - Data to cache
   * @param {number} ttl - Time to live in milliseconds
   */
  set(key, data, ttl = APP_CONFIG.CACHE.WEATHER_TTL) {
    // Remove oldest items if cache is full
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }

    const expires = Date.now() + ttl;
    this.cache.set(key, { data, expires });

    if (PERFORMANCE.LOG_CACHE_HITS) {
      console.log(`[Cache Set] ${key} (expires: ${new Date(expires).toLocaleTimeString()})`);
    }
  }

  /**
   * Clear expired items from cache
   */
  cleanup() {
    const now = Date.now();
    for (const [key, item] of this.cache.entries()) {
      if (now > item.expires) {
        this.cache.delete(key);
      }
    }
  }

  /**
   * Clear all items from cache
   */
  clear() {
    this.cache.clear();
  }

  /**
   * Get cache statistics
   * @returns {Object} - Cache statistics
   */
  getStats() {
    const now = Date.now();
    let expired = 0;
    let valid = 0;

    for (const item of this.cache.values()) {
      if (now > item.expires) {
        expired++;
      } else {
        valid++;
      }
    }

    return {
      total: this.cache.size,
      valid,
      expired,
      maxSize: this.maxSize
    };
  }
}

// Global cache instance
export const apiCache = new APICache();

/**
 * Cached GET request
 * @param {string} url - Request URL
 * @param {Object} params - Query parameters
 * @param {Object} options - Request options including cache TTL
 * @returns {Promise<any>} - Cached or fresh data
 */
export const getCached = async (url, params = {}, options = {}) => {
  const {
    cacheTTL = APP_CONFIG.CACHE.WEATHER_TTL,
    forceRefresh = false,
    ...requestOptions
  } = options;

  const cacheKey = apiCache.generateKey(url, params);

  // Return cached data if available and not forcing refresh
  if (!forceRefresh && FEATURES.ENABLE_CACHING) {
    const cachedData = apiCache.get(cacheKey);
    if (cachedData) {
      return cachedData;
    }
  }

  // Fetch fresh data
  const fullUrl = buildURL(url, params);
  const data = await get(fullUrl, requestOptions);

  // Cache the response
  if (FEATURES.ENABLE_CACHING) {
    apiCache.set(cacheKey, data, cacheTTL);
  }

  return data;
};

/**
 * Initialize API utilities
 * Set up event listeners and cleanup routines
 */
export const initializeAPI = () => {
  // Clean up cache periodically
  if (FEATURES.ENABLE_CACHING) {
    setInterval(() => {
      apiCache.cleanup();
    }, 5 * 60 * 1000); // Every 5 minutes
  }

  // Listen for online/offline events
  window.addEventListener('online', () => {
    if (FEATURES.DEBUG_MODE) {
      console.log('[Network] Back online');
    }
  });

  window.addEventListener('offline', () => {
    if (FEATURES.DEBUG_MODE) {
      console.log('[Network] Gone offline');
    }
  });

  // Log initialization
  if (FEATURES.DEBUG_MODE) {
    console.log('[API] Utilities initialized', {
      caching: FEATURES.ENABLE_CACHING,
      rateLimit: rateLimiter.maxRequests + ' requests per minute',
      timeout: APP_CONFIG.REQUESTS.TIMEOUT + 'ms',
      retries: APP_CONFIG.REQUESTS.RETRY_ATTEMPTS
    });
  }
};

// Auto-initialize when module is imported
if (typeof window !== 'undefined') {
  // Initialize on next tick to allow other modules to load
  setTimeout(initializeAPI, 0);
}

export default {
  APIError,
  get,
  post,
  getCached,
  buildURL,
  isValidURL,
  fetchWithRetry,
  sleep,
  isOnline,
  apiCache,
  initializeAPI
};