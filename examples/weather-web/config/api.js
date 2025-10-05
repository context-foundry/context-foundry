/**
 * API Configuration
 * PROBLEM: All configurations set for premium tier
 */

// ISSUE: Premium tier configuration
export const API_CONFIG = {
  // Premium weather API configuration
  weather: {
    baseUrl: 'https://api.weatherapi.com/v1/premium',
    tier: 'premium',
    features: [
      'current',
      'forecast',
      'history',      // Premium only
      'astronomy',
      'sports',       // Premium only
      'alerts',       // Premium only
      'air_quality'   // Premium only
    ],
    limits: {
      requestsPerMonth: 1000000,  // Premium limit
      requestsPerDay: 50000,      // Premium limit
      requestsPerHour: 5000,      // Premium limit
      forecastDays: 14,           // Premium: up to 14 days
      historyDays: 365            // Premium: full year history
    },
    timeout: 15000  // Premium service timeout
  },

  // PROBLEM: Premium authentication
  auth: {
    type: 'api_key',
    keyParam: 'key',
    tier: 'premium',
    subscriptionLevel: 'pro_plus'
  },

  // Premium retry configuration
  retry: {
    attempts: 5,        // Premium: more retries
    backoffMs: 1000,
    maxBackoffMs: 10000
  },

  // Premium caching strategy
  cache: {
    enabled: true,
    ttl: {
      current: 300000,    // 5 minutes for premium
      forecast: 3600000,  // 1 hour for premium
      history: 86400000   // 24 hours for premium
    }
  }
};

// PROBLEM: Environment-specific premium configs
export const ENVIRONMENT_CONFIGS = {
  development: {
    ...API_CONFIG,
    debug: true,
    mockData: false  // Premium: use real API in dev
  },
  
  production: {
    ...API_CONFIG,
    debug: false,
    timeout: 20000,  // Premium production timeout
    retry: {
      ...API_CONFIG.retry,
      attempts: 10   // Premium: more retries in prod
    }
  },

  testing: {
    ...API_CONFIG,
    baseUrl: 'https://api.weatherapi.com/v1/premium-sandbox',
    mockData: true
  }
};

// Get configuration for current environment
export const getCurrentConfig = () => {
  const env = process.env.NODE_ENV || 'development';
  return ENVIRONMENT_CONFIGS[env] || ENVIRONMENT_CONFIGS.development;
};

// PROBLEM: Premium-specific constants
export const PREMIUM_FEATURES = {
  EXTENDED_FORECAST: 'extended_forecast',
  AIR_QUALITY: 'air_quality',
  WEATHER_ALERTS: 'weather_alerts',
  HISTORICAL_DATA: 'historical_data',
  SPORTS_DATA: 'sports_data',
  ASTRONOMY_DATA: 'astronomy_data',
  HOURLY_FORECAST: 'hourly_forecast'
};

// Premium API endpoints
export const PREMIUM_ENDPOINTS = {
  current: '/current.json',
  forecast: '/forecast.json',
  history: '/history.json',
  future: '/future.json',
  astronomy: '/astronomy.json',
  sports: '/sports.json',
  alerts: '/alerts.json',
  search: '/search.json'
};