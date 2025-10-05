/**
 * Error Handler Utility
 * Comprehensive error handling system with user-friendly messages and retry mechanisms
 */

import { ERROR_MESSAGES, APP_CONFIG, FEATURES } from '../constants/config.js';

/**
 * Error types enum
 */
export const ERROR_TYPES = {
  NETWORK: 'network',
  API: 'api',
  GEOLOCATION: 'geolocation',
  STORAGE: 'storage',
  VALIDATION: 'validation',
  AUTHENTICATION: 'authentication',
  RATE_LIMIT: 'rate_limit',
  TIMEOUT: 'timeout',
  PARSE: 'parse',
  UNKNOWN: 'unknown'
};

/**
 * Error severity levels
 */
export const ERROR_SEVERITY = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical'
};

/**
 * Retry strategies
 */
export const RETRY_STRATEGIES = {
  NONE: 'none',
  IMMEDIATE: 'immediate',
  EXPONENTIAL: 'exponential',
  LINEAR: 'linear',
  CUSTOM: 'custom'
};

/**
 * Custom error class with enhanced functionality
 */
export class AppError extends Error {
  constructor(message, type = ERROR_TYPES.UNKNOWN, options = {}) {
    super(message);
    this.name = 'AppError';
    this.type = type;
    this.severity = options.severity || ERROR_SEVERITY.MEDIUM;
    this.code = options.code || 0;
    this.statusCode = options.statusCode || null;
    this.timestamp = new Date();
    this.retryable = options.retryable !== false;
    this.userMessage = options.userMessage || this.getUserFriendlyMessage();
    this.context = options.context || {};
    this.source = options.source || 'unknown';
    this.stack = Error.captureStackTrace ? Error.captureStackTrace(this, AppError) : (new Error()).stack;
    
    // Retry configuration
    this.maxRetries = options.maxRetries || 3;
    this.retryStrategy = options.retryStrategy || RETRY_STRATEGIES.EXPONENTIAL;
    this.retryDelay = options.retryDelay || 1000;
    this.currentRetry = 0;
  }

  /**
   * Get user-friendly error message
   * @returns {string} - User-friendly message
   */
  getUserFriendlyMessage() {
    const messages = ERROR_MESSAGES[this.type.toUpperCase()];
    if (messages) {
      return messages.GENERIC || messages.DEFAULT || this.message;
    }
    return ERROR_MESSAGES.GENERIC || 'An unexpected error occurred';
  }

  /**
   * Check if error is retryable
   * @returns {boolean} - Whether error can be retried
   */
  canRetry() {
    return this.retryable && this.currentRetry < this.maxRetries;
  }

  /**
   * Increment retry count
   */
  incrementRetry() {
    this.currentRetry++;
  }

  /**
   * Get retry delay for current attempt
   * @returns {number} - Delay in milliseconds
   */
  getRetryDelay() {
    switch (this.retryStrategy) {
      case RETRY_STRATEGIES.IMMEDIATE:
        return 0;
      
      case RETRY_STRATEGIES.LINEAR:
        return this.retryDelay * this.currentRetry;
      
      case RETRY_STRATEGIES.EXPONENTIAL:
        return this.retryDelay * Math.pow(2, this.currentRetry);
      
      default:
        return this.retryDelay;
    }
  }

  /**
   * Convert error to JSON for logging
   * @returns {Object} - Error object
   */
  toJSON() {
    return {
      name: this.name,
      message: this.message,
      userMessage: this.userMessage,
      type: this.type,
      severity: this.severity,
      code: this.code,
      statusCode: this.statusCode,
      timestamp: this.timestamp,
      retryable: this.retryable,
      currentRetry: this.currentRetry,
      maxRetries: this.maxRetries,
      context: this.context,
      source: this.source,
      stack: this.stack
    };
  }
}

/**
 * Network Error class for API-related errors
 */
export class NetworkError extends AppError {
  constructor(message, statusCode, options = {}) {
    super(message, ERROR_TYPES.NETWORK, {
      ...options,
      statusCode,
      severity: options.severity || ERROR_SEVERITY.HIGH
    });
    this.name = 'NetworkError';
  }
}

/**
 * API Error class for weather API errors
 */
export class APIError extends AppError {
  constructor(message, code, options = {}) {
    super(message, ERROR_TYPES.API, {
      ...options,
      code,
      severity: options.severity || ERROR_SEVERITY.MEDIUM
    });
    this.name = 'APIError';
  }
}

/**
 * Error Handler Class
 * Centralized error handling with reporting, retry, and user notification
 */
export class ErrorHandler {
  constructor(options = {}) {
    this.options = {
      enableReporting: true,
      enableRetry: true,
      enableUserNotification: true,
      enableLogging: FEATURES.DEBUG_MODE,
      maxErrorHistory: 50,
      ...options
    };

    // Error history for debugging and analytics
    this.errorHistory = [];
    
    // Retry queue for failed operations
    this.retryQueue = new Map();
    
    // Error listeners
    this.listeners = new Map();
    
    // Global error handlers
    this.setupGlobalHandlers();
    
    // Bind methods
    this.handleError = this.handleError.bind(this);
    this.retry = this.retry.bind(this);
    this.createUserNotification = this.createUserNotification.bind(this);

    if (FEATURES.DEBUG_MODE) {
      console.log('[ErrorHandler] Initialized');
      this.enableDebugMode();
    }
  }

  /**
   * Setup global error handlers
   */
  setupGlobalHandlers() {
    // Unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.handleError(
        new AppError(
          event.reason?.message || 'Unhandled promise rejection',
          ERROR_TYPES.UNKNOWN,
          {
            severity: ERROR_SEVERITY.HIGH,
            context: { reason: event.reason },
            source: 'unhandledrejection'
          }
        )
      );
    });

    // Global JavaScript errors
    window.addEventListener('error', (event) => {
      this.handleError(
        new AppError(
          event.message || 'JavaScript error',
          ERROR_TYPES.UNKNOWN,
          {
            severity: ERROR_SEVERITY.HIGH,
            context: {
              filename: event.filename,
              lineno: event.lineno,
              colno: event.colno,
              error: event.error
            },
            source: 'javascript'
          }
        )
      );
    });

    // Network connectivity errors
    window.addEventListener('offline', () => {
      this.handleError(
        new AppError(
          'Network connection lost',
          ERROR_TYPES.NETWORK,
          {
            severity: ERROR_SEVERITY.MEDIUM,
            userMessage: 'You are currently offline. Some features may not work.',
            source: 'connectivity'
          }
        )
      );
    });
  }

  /**
   * Main error handling method
   * @param {Error|AppError} error - Error to handle
   * @param {Object} options - Handling options
   * @returns {Promise<boolean>} - Whether error was handled successfully
   */
  async handleError(error, options = {}) {
    try {
      // Convert to AppError if needed
      const appError = this.normalizeError(error, options);
      
      // Add to error history
      this.addToHistory(appError);
      
      // Log error if enabled
      if (this.options.enableLogging) {
        this.logError(appError);
      }
      
      // Notify listeners
      this.notifyListeners(appError);
      
      // Show user notification if enabled
      if (this.options.enableUserNotification && options.showUser !== false) {
        this.createUserNotification(appError);
      }
      
      // Handle retry logic if enabled
      if (this.options.enableRetry && appError.canRetry() && options.retry !== false) {
        return await this.scheduleRetry(appError, options.retryCallback);
      }
      
      // Report error if enabled
      if (this.options.enableReporting && options.report !== false) {
        this.reportError(appError);
      }
      
      return true;
    } catch (handlerError) {
      console.error('[ErrorHandler] Error in error handler:', handlerError);
      return false;
    }
  }

  /**
   * Convert any error to AppError
   * @param {Error} error - Original error
   * @param {Object} options - Conversion options
   * @returns {AppError} - Normalized error
   */
  normalizeError(error, options = {}) {
    if (error instanceof AppError) {
      return error;
    }

    // Detect error type based on properties
    let type = ERROR_TYPES.UNKNOWN;
    let severity = ERROR_SEVERITY.MEDIUM;
    let code = 0;
    let statusCode = null;

    // Network/HTTP errors
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      type = ERROR_TYPES.NETWORK;
      severity = ERROR_SEVERITY.HIGH;
    } else if (error.status || error.statusCode) {
      type = ERROR_TYPES.API;
      statusCode = error.status || error.statusCode;
      code = statusCode;
    } else if (error.name === 'GeolocationError' || error.code >= 1 && error.code <= 3) {
      type = ERROR_TYPES.GEOLOCATION;
      code = error.code;
    } else if (error.name === 'QuotaExceededError' || error.name === 'SecurityError') {
      type = ERROR_TYPES.STORAGE;
    } else if (error.name === 'SyntaxError' || error.name === 'TypeError') {
      type = ERROR_TYPES.PARSE;
    } else if (error.name === 'TimeoutError' || error.message.includes('timeout')) {
      type = ERROR_TYPES.TIMEOUT;
      severity = ERROR_SEVERITY.MEDIUM;
    }

    return new AppError(
      error.message || 'An error occurred',
      type,
      {
        severity,
        code,
        statusCode,
        context: { originalError: error },
        source: options.source || 'normalized',
        ...options
      }
    );
  }

  /**
   * Schedule retry for failed operation
   * @param {AppError} error - Error to retry
   * @param {Function} retryCallback - Function to retry
   * @returns {Promise<boolean>} - Retry result
   */
  async scheduleRetry(error, retryCallback) {
    if (!error.canRetry() || !retryCallback) {
      return false;
    }

    const retryId = `retry_${Date.now()}_${Math.random()}`;
    const delay = error.getRetryDelay();

    // Add to retry queue
    this.retryQueue.set(retryId, {
      error,
      callback: retryCallback,
      delay,
      scheduled: Date.now()
    });

    if (FEATURES.DEBUG_MODE) {
      console.log(`[ErrorHandler] Scheduling retry ${error.currentRetry + 1}/${error.maxRetries} in ${delay}ms`);
    }

    // Schedule retry
    return new Promise((resolve) => {
      setTimeout(async () => {
        try {
          error.incrementRetry();
          const result = await retryCallback();
          
          // Remove from retry queue on success
          this.retryQueue.delete(retryId);
          
          if (FEATURES.DEBUG_MODE) {
            console.log('[ErrorHandler] Retry successful');
          }
          
          resolve(true);
        } catch (retryError) {
          // Handle retry failure
          const normalizedRetryError = this.normalizeError(retryError, {
            source: 'retry',
            context: { originalError: error, retryAttempt: error.currentRetry }
          });
          
          if (error.canRetry()) {
            // Schedule another retry
            resolve(await this.scheduleRetry(error, retryCallback));
          } else {
            // Max retries reached
            this.retryQueue.delete(retryId);
            
            if (FEATURES.DEBUG_MODE) {
              console.log(`[ErrorHandler] Max retries reached for error: ${error.message}`);
            }
            
            // Show final error to user
            this.createUserNotification(normalizedRetryError, { isFinal: true });
            resolve(false);
          }
        }
      }, delay);
    });
  }

  /**
   * Create user notification for error
   * @param {AppError} error - Error to notify about
   * @param {Object} options - Notification options
   */
  createUserNotification(error, options = {}) {
    const { 
      duration = this.getNotificationDuration(error.severity),
      showRetry = error.canRetry() && !options.isFinal,
      type = 'error',
      position = 'top-right'
    } = options;

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `error-notification error-${error.severity} notification-${type}`;
    notification.setAttribute('role', 'alert');
    notification.setAttribute('aria-live', 'polite');

    // Notification content
    const content = document.createElement('div');
    content.className = 'notification-content';

    // Error icon
    const icon = document.createElement('div');
    icon.className = 'notification-icon';
    icon.innerHTML = this.getErrorIcon(error.type, error.severity);

    // Error message
    const message = document.createElement('div');
    message.className = 'notification-message';
    message.textContent = error.userMessage;

    // Error details (collapsible, for debug mode)
    if (FEATURES.DEBUG_MODE) {
      const details = document.createElement('details');
      details.className = 'notification-details';
      
      const summary = document.createElement('summary');
      summary.textContent = 'Technical Details';
      
      const detailsContent = document.createElement('pre');
      detailsContent.textContent = JSON.stringify(error.toJSON(), null, 2);
      
      details.appendChild(summary);
      details.appendChild(detailsContent);
      content.appendChild(details);
    }

    // Action buttons
    const actions = document.createElement('div');
    actions.className = 'notification-actions';

    // Retry button
    if (showRetry) {
      const retryButton = document.createElement('button');
      retryButton.className = 'notification-retry';
      retryButton.textContent = 'Retry';
      retryButton.addEventListener('click', () => {
        this.dismissNotification(notification);
        // Trigger retry if callback available
        if (options.retryCallback) {
          this.retry(error, options.retryCallback);
        }
      });
      actions.appendChild(retryButton);
    }

    // Dismiss button
    const dismissButton = document.createElement('button');
    dismissButton.className = 'notification-dismiss';
    dismissButton.setAttribute('aria-label', 'Dismiss notification');
    dismissButton.innerHTML = '×';
    dismissButton.addEventListener('click', () => {
      this.dismissNotification(notification);
    });
    actions.appendChild(dismissButton);

    // Assemble notification
    content.appendChild(icon);
    content.appendChild(message);
    notification.appendChild(content);
    notification.appendChild(actions);

    // Add to DOM
    this.showNotification(notification, { duration, position });

    // Return notification element for external control
    return notification;
  }

  /**
   * Show notification in the UI
   * @param {HTMLElement} notification - Notification element
   * @param {Object} options - Show options
   */
  showNotification(notification, options = {}) {
    const { duration, position } = options;

    // Get or create notification container
    let container = document.querySelector('.error-notifications');
    if (!container) {
      container = document.createElement('div');
      container.className = `error-notifications notifications-${position}`;
      document.body.appendChild(container);
    }

    // Add notification
    container.appendChild(notification);

    // Trigger entrance animation
    setTimeout(() => {
      notification.classList.add('notification-show');
    }, 10);

    // Auto-dismiss if duration specified
    if (duration > 0) {
      setTimeout(() => {
        this.dismissNotification(notification);
      }, duration);
    }
  }

  /**
   * Dismiss notification
   * @param {HTMLElement} notification - Notification to dismiss
   */
  dismissNotification(notification) {
    notification.classList.add('notification-hide');
    
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300); // Match CSS animation duration
  }

  /**
   * Get notification duration based on severity
   * @param {string} severity - Error severity
   * @returns {number} - Duration in milliseconds
   */
  getNotificationDuration(severity) {
    switch (severity) {
      case ERROR_SEVERITY.LOW:
        return 3000;
      case ERROR_SEVERITY.MEDIUM:
        return 5000;
      case ERROR_SEVERITY.HIGH:
        return 8000;
      case ERROR_SEVERITY.CRITICAL:
        return 0; // Don't auto-dismiss critical errors
      default:
        return 5000;
    }
  }

  /**
   * Get appropriate icon for error type and severity
   * @param {string} type - Error type
   * @param {string} severity - Error severity
   * @returns {string} - Icon HTML
   */
  getErrorIcon(type, severity) {
    const icons = {
      [ERROR_TYPES.NETWORK]: '🌐',
      [ERROR_TYPES.API]: '⚠️',
      [ERROR_TYPES.GEOLOCATION]: '📍',
      [ERROR_TYPES.STORAGE]: '💾',
      [ERROR_TYPES.VALIDATION]: '❌',
      [ERROR_TYPES.TIMEOUT]: '⏱️',
      [ERROR_TYPES.RATE_LIMIT]: '🚦',
      [ERROR_TYPES.UNKNOWN]: '❓'
    };

    const severityIcons = {
      [ERROR_SEVERITY.LOW]: '💡',
      [ERROR_SEVERITY.MEDIUM]: '⚠️',
      [ERROR_SEVERITY.HIGH]: '🚨',
      [ERROR_SEVERITY.CRITICAL]: '💀'
    };

    return icons[type] || severityIcons[severity] || '❓';
  }

  /**
   * Add error to history
   * @param {AppError} error - Error to add
   */
  addToHistory(error) {
    this.errorHistory.unshift(error);
    
    // Limit history size
    if (this.errorHistory.length > this.options.maxErrorHistory) {
      this.errorHistory = this.errorHistory.slice(0, this.options.maxErrorHistory);
    }
  }

  /**
   * Log error to console
   * @param {AppError} error - Error to log
   */
  logError(error) {
    const logMethod = this.getLogMethod(error.severity);
    const errorData = error.toJSON();
    
    logMethod(`[ErrorHandler] ${error.type.toUpperCase()} Error:`, errorData);
    
    if (error.stack) {
      console.trace('[ErrorHandler] Stack trace:', error.stack);
    }
  }

  /**
   * Get appropriate console method for severity
   * @param {string} severity - Error severity
   * @returns {Function} - Console method
   */
  getLogMethod(severity) {
    switch (severity) {
      case ERROR_SEVERITY.LOW:
        return console.info;
      case ERROR_SEVERITY.MEDIUM:
        return console.warn;
      case ERROR_SEVERITY.HIGH:
      case ERROR_SEVERITY.CRITICAL:
        return console.error;
      default:
        return console.log;
    }
  }

  /**
   * Notify error listeners
   * @param {AppError} error - Error to notify about
   */
  notifyListeners(error) {
    this.listeners.forEach((callback, id) => {
      try {
        callback(error);
      } catch (listenerError) {
        console.error(`[ErrorHandler] Listener error (${id}):`, listenerError);
      }
    });
  }

  /**
   * Report error to external service (placeholder)
   * @param {AppError} error - Error to report
   */
  reportError(error) {
    if (!this.options.enableReporting) return;

    // Placeholder for external error reporting service
    if (FEATURES.DEBUG_MODE) {
      console.log('[ErrorHandler] Reporting error:', error.toJSON());
    }

    // Example: Send to error reporting service
    // fetch('/api/errors', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(error.toJSON())
    // }).catch(() => {
    //   // Silent fail for error reporting
    // });
  }

  /**
   * Subscribe to error events
   * @param {Function} callback - Error callback
   * @returns {string} - Subscription ID
   */
  subscribe(callback) {
    const id = `listener_${Date.now()}_${Math.random()}`;
    this.listeners.set(id, callback);
    return id;
  }

  /**
   * Unsubscribe from error events
   * @param {string} id - Subscription ID
   */
  unsubscribe(id) {
    this.listeners.delete(id);
  }

  /**
   * Retry operation manually
   * @param {AppError} error - Error to retry
   * @param {Function} retryCallback - Function to retry
   * @returns {Promise<boolean>} - Retry result
   */
  async retry(error, retryCallback) {
    return await this.scheduleRetry(error, retryCallback);
  }

  /**
   * Clear error history
   */
  clearHistory() {
    this.errorHistory = [];
  }

  /**
   * Get error statistics
   * @returns {Object} - Error statistics
   */
  getStatistics() {
    const typeCount = {};
    const severityCount = {};
    
    this.errorHistory.forEach(error => {
      typeCount[error.type] = (typeCount[error.type] || 0) + 1;
      severityCount[error.severity] = (severityCount[error.severity] || 0) + 1;
    });

    return {
      totalErrors: this.errorHistory.length,
      typeCount,
      severityCount,
      retryQueueSize: this.retryQueue.size,
      listenerCount: this.listeners.size
    };
  }

  /**
   * Enable debug mode with enhanced logging
   */
  enableDebugMode() {
    // Add global error handler stats to window
    window._errorHandler = this;
    
    // Enhanced logging
    this.subscribe((error) => {
      console.group(`[ErrorHandler] Error Handled - ${error.type}`);
      console.log('Error:', error);
      console.log('Statistics:', this.getStatistics());
      console.log('Retry Queue:', Array.from(this.retryQueue.entries()));
      console.groupEnd();
    });
  }

  /**
   * Cleanup resources
   */
  destroy() {
    // Clear retry queue
    this.retryQueue.forEach((retry, id) => {
      clearTimeout(retry.timeoutId);
    });
    this.retryQueue.clear();

    // Clear listeners
    this.listeners.clear();

    // Clear history
    this.errorHistory = [];

    // Remove global handlers would need references stored
    // This is simplified - in production you'd store the handler references

    if (FEATURES.DEBUG_MODE) {
      console.log('[ErrorHandler] Destroyed');
    }
  }
}

// Create singleton instance
export const errorHandler = new ErrorHandler();

// Export convenience functions
export const handleError = errorHandler.handleError.bind(errorHandler);
export const createError = (message, type, options) => new AppError(message, type, options);
export const createNetworkError = (message, statusCode, options) => new NetworkError(message, statusCode, options);
export const createAPIError = (message, code, options) => new APIError(message, code, options);

// Export error handling utilities
export const withErrorHandling = (asyncFn, options = {}) => {
  return async (...args) => {
    try {
      return await asyncFn(...args);
    } catch (error) {
      await handleError(error, options);
      throw error;
    }
  };
};

export const catchAsync = withErrorHandling;

export default errorHandler;