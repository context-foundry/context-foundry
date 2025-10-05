/**
 * Free Tier Migration Helper
 * Maps premium configurations to free tier equivalents
 */

import { 
  FREE_TIER_CONFIG, 
  FREE_TIER_ENDPOINTS, 
  FREE_TIER_ERROR_CODES,
  FREE_TIER_BEST_PRACTICES 
} from './freeTierAPI.js';

/**
 * Migration mapping from premium to free tier
 */
export const MIGRATION_MAPPING = {
  // URL transformations
  urls: {
    'https://api.weatherapi.com/v1/premium': 'https://api.weatherapi.com/v1',
    '/v1/premium/': '/v1/',
    '/premium/': '/'
  },
  
  // Parameter transformations
  parameters: {
    // Remove premium-only parameters
    remove: ['alerts', 'air_quality', 'sports'],
    
    // Transform parameter values
    transform: {
      aqi: 'no',        // Always 'no' for free tier
      alerts: 'no',     // Always 'no' for free tier  
      days: (value) => Math.min(value, 3),  // Max 3 days
    },
    
    // Default values for free tier
    defaults: {
      aqi: 'no',
      alerts: 'no',
      lang: 'en'
    }
  },
  
  // Response field mapping
  responseFields: {
    // Fields to remove from premium responses
    remove: [
      'air_quality',
      'alerts', 
      'sports',
      'marine'
    ],
    
    // Fields that may be null in free tier
    nullable: [
      'current.air_quality',
      'alerts',
      'forecast.forecastday[].day.air_quality'
    ]
  },
  
  // Feature availability mapping
  features: {
    current: 'available',
    forecast: 'limited',      // Limited to 3 days
    history: 'limited',       // Limited to 7 days
    search: 'available',
    astronomy: 'available',
    alerts: 'unavailable',
    air_quality: 'unavailable',
    sports: 'unavailable',
    marine: 'unavailable'
  }
};

/**
 * Transform premium URL to free tier URL
 * @param {string} premiumUrl - Premium API URL
 * @returns {string} Free tier URL
 */
export const transformUrl = (premiumUrl) => {
  let freeUrl = premiumUrl;
  
  Object.entries(MIGRATION_MAPPING.urls).forEach(([premium, free]) => {
    freeUrl = freeUrl.replace(premium, free);
  });
  
  return freeUrl;
};

/**
 * Transform premium parameters to free tier parameters
 * @param {Object} premiumParams - Premium API parameters
 * @returns {Object} Free tier parameters
 */
export const transformParameters = (premiumParams) => {
  const freeParams = { ...premiumParams };
  
  // Remove premium-only parameters
  MIGRATION_MAPPING.parameters.remove.forEach(param => {
    delete freeParams[param];
  });
  
  // Transform parameter values
  Object.entries(MIGRATION_MAPPING.parameters.transform).forEach(([param, transformer]) => {
    if (freeParams[param] !== undefined) {
      if (typeof transformer === 'function') {
        freeParams[param] = transformer(freeParams[param]);
      } else {
        freeParams[param] = transformer;
      }
    }
  });
  
  // Apply default values
  Object.entries(MIGRATION_MAPPING.parameters.defaults).forEach(([param, defaultValue]) => {
    if (freeParams[param] === undefined) {
      freeParams[param] = defaultValue;
    }
  });
  
  return freeParams;
};

/**
 * Transform premium response to free tier format
 * @param {Object} premiumResponse - Premium API response
 * @returns {Object} Free tier compatible response
 */
export const transformResponse = (premiumResponse) => {
  const freeResponse = JSON.parse(JSON.stringify(premiumResponse));
  
  // Remove premium-only fields recursively
  const removeFields = (obj, fieldsToRemove) => {
    if (!obj || typeof obj !== 'object') return obj;
    
    fieldsToRemove.forEach(field => {
      if (field.includes('[].')) {
        // Handle array fields like 'forecast.forecastday[].day.air_quality'
        const [parentPath, childField] = field.split('[].', 2);
        const parent = getNestedValue(obj, parentPath);
        if (Array.isArray(parent)) {
          parent.forEach(item => {
            deleteNestedValue(item, childField);
          });
        }
      } else {
        deleteNestedValue(obj, field);
      }
    });
    
    return obj;
  };
  
  return removeFields(freeResponse, MIGRATION_MAPPING.responseFields.remove);
};

/**
 * Get nested object value by dot notation path
 * @param {Object} obj - Source object
 * @param {string} path - Dot notation path
 * @returns {*} Value at path
 */
const getNestedValue = (obj, path) => {
  return path.split('.').reduce((current, key) => current?.[key], obj);
};

/**
 * Delete nested object value by dot notation path
 * @param {Object} obj - Source object  
 * @param {string} path - Dot notation path
 */
const deleteNestedValue = (obj, path) => {
  const keys = path.split('.');
  const lastKey = keys.pop();
  const parent = keys.reduce((current, key) => current?.[key], obj);
  
  if (parent && typeof parent === 'object') {
    delete parent[lastKey];
  }
};

/**
 * Validate request is compatible with free tier
 * @param {string} endpoint - API endpoint
 * @param {Object} params - Request parameters
 * @returns {Object} Validation result
 */
export const validateFreeTierRequest = (endpoint, params) => {
  const errors = [];
  const warnings = [];
  
  // Check endpoint availability
  const endpointName = endpoint.split('/').pop().replace('.json', '');
  const featureStatus = MIGRATION_MAPPING.features[endpointName];
  
  if (featureStatus === 'unavailable') {
    errors.push(`Endpoint '${endpointName}' is not available in free tier`);
  } else if (featureStatus === 'limited') {
    warnings.push(`Endpoint '${endpointName}' has limitations in free tier`);
  }
  
  // Check forecast days limit
  if (params.days && params.days > 3) {
    errors.push(`Forecast days limited to 3 in free tier, requested: ${params.days}`);
  }
  
  // Check for premium parameters
  if (params.aqi === 'yes') {
    errors.push('Air quality data (aqi=yes) not available in free tier');
  }
  
  if (params.alerts === 'yes') {
    errors.push('Weather alerts (alerts=yes) not available in free tier');
  }
  
  // Check API key format (basic validation)
  if (!params.key || params.key.includes('premium')) {
    warnings.push('API key may be configured for premium tier');
  }
  
  return {
    isValid: errors.length === 0,
    errors,
    warnings
  };
};

/**
 * Generate free tier configuration from premium config
 * @param {Object} premiumConfig - Premium configuration
 * @returns {Object} Free tier configuration
 */
export const generateFreeTierConfig = (premiumConfig) => {
  return {
    ...FREE_TIER_CONFIG,
    
    // Override with environment-specific settings
    apiKey: premiumConfig.apiKey, // Keep same API key format
    environment: premiumConfig.environment,
    debug: premiumConfig.debug,
    
    // Apply free tier limits
    limits: FREE_TIER_CONFIG.limits,
    
    // Use free tier endpoints
    endpoints: FREE_TIER_ENDPOINTS,
    
    // Apply free tier request config
    requestConfig: {
      ...premiumConfig.requestConfig,
      ...FREE_TIER_CONFIG.requestConfig,
      timeout: Math.min(premiumConfig.requestConfig?.timeout || 15000, 10000)
    },
    
    // Use free tier best practices
    cache: FREE_TIER_BEST_PRACTICES.caching,
    rateLimiting: FREE_TIER_BEST_PRACTICES.rateLimiting,
    errorHandling: FREE_TIER_BEST_PRACTICES.errorHandling
  };
};

export default {
  MIGRATION_MAPPING,
  transformUrl,
  transformParameters,
  transformResponse,
  validateFreeTierRequest,
  generateFreeTierConfig
};