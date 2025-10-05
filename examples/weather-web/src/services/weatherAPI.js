/**
 * Weather API Service
 * Currently configured for PAID tier - causing loading issues
 * TODO: Switch to free tier endpoint
 */

// PROBLEM: Using paid tier endpoint
const API_BASE_URL = 'https://api.weatherapi.com/v1/premium';
const API_KEY = process.env.REACT_APP_WEATHER_API_KEY || 'your-paid-api-key-here';

// PROBLEM: Premium features in request parameters
const DEFAULT_PARAMS = {
  key: API_KEY,
  aqi: 'yes',        // Air quality - premium feature
  alerts: 'yes',     // Weather alerts - premium feature  
  days: 10,          // 10-day forecast - premium feature
  lang: 'en',
  units: 'metric'
};

/**
 * Weather API endpoints configuration
 * ISSUE: All using premium tier URLs
 */
const ENDPOINTS = {
  current: `${API_BASE_URL}/current.json`,
  forecast: `${API_BASE_URL}/forecast.json`,
  history: `${API_BASE_URL}/history.json`,  // Premium only
  astronomy: `${API_BASE_URL}/astronomy.json`,
  sports: `${API_BASE_URL}/sports.json`,    // Premium only
  alerts: `${API_BASE_URL}/alerts.json`     // Premium only
};

/**
 * Request configuration for paid tier
 * PROBLEM: Includes premium headers and timeout for paid service
 */
const REQUEST_CONFIG = {
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    'X-Subscription-Tier': 'premium',  // Premium header
    'X-Rate-Limit': 'unlimited'        // Premium rate limit
  }
};

/**
 * Build API URL with parameters
 * @param {string} endpoint - API endpoint
 * @param {Object} params - Additional parameters
 * @returns {string} Complete API URL
 */
const buildApiUrl = (endpoint, params = {}) => {
  const allParams = { ...DEFAULT_PARAMS, ...params };
  const queryString = new URLSearchParams(allParams).toString();
  return `${endpoint}?${queryString}`;
};

/**
 * Validate API response
 * PROBLEM: Expects premium tier response format
 * @param {Object} response - API response
 * @returns {boolean} Is valid response
 */
const validateResponse = (response) => {
  if (!response || !response.data) {
    return false;
  }
  
  // ISSUE: Checking for premium-only fields
  const data = response.data;
  return data.current && 
         data.location && 
         data.alerts &&     // Premium field
         data.forecast &&
         data.forecast.forecastday &&
         data.forecast.forecastday.length >= 10;  // Premium: 10+ days
};

export {
  API_BASE_URL,
  API_KEY,
  ENDPOINTS,
  REQUEST_CONFIG,
  DEFAULT_PARAMS,
  buildApiUrl,
  validateResponse
};