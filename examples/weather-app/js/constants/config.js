/**
 * Application Configuration
 * Contains API keys, endpoints, and global settings
 */

// OpenWeatherMap API Configuration
export const WEATHER_API = {
  API_KEY: 'c4b27d06b0817cd09f83aa58745fda97',
  BASE_URL: 'https://api.openweathermap.org/data/2.5',
  GEO_URL: 'https://api.openweathermap.org/geo/1.0',
  ICON_URL: 'https://openweathermap.org/img/wn',
  
  // API Endpoints
  ENDPOINTS: {
    CURRENT_WEATHER: '/weather',
    FORECAST: '/forecast',
    DIRECT_GEOCODING: '/direct',
    REVERSE_GEOCODING: '/reverse',
    ONE_CALL: '/onecall'
  },
  
  // API Limits and constraints
  RATE_LIMIT: {
    CALLS_PER_MINUTE: 60,
    CALLS_PER_DAY: 1000,
    BURST_LIMIT: 10
  },
  
  // Default parameters
  DEFAULT_PARAMS: {
    units: 'metric', // metric, imperial, kelvin
    lang: 'en',
    cnt: 5 // forecast days
  }
};

// Application Settings
export const APP_CONFIG = {
  // Cache settings
  CACHE: {
    WEATHER_TTL: 15 * 60 * 1000, // 15 minutes in milliseconds
    FORECAST_TTL: 60 * 60 * 1000, // 1 hour in milliseconds
    GEOCODING_TTL: 24 * 60 * 60 * 1000, // 24 hours in milliseconds
    MAX_CACHE_SIZE: 50, // Maximum number of cached items
    STORAGE_KEY: 'weather_app_cache'
  },
  
  // Request settings
  REQUESTS: {
    TIMEOUT: 10000, // 10 seconds
    RETRY_ATTEMPTS: 3,
    RETRY_DELAY: 1000, // 1 second base delay
    RETRY_BACKOFF: 2 // exponential backoff multiplier
  },
  
  // Geolocation settings
  GEOLOCATION: {
    TIMEOUT: 10000, // 10 seconds
    MAXIMUM_AGE: 5 * 60 * 1000, // 5 minutes
    ENABLE_HIGH_ACCURACY: false
  },
  
  // Search settings
  SEARCH: {
    MIN_QUERY_LENGTH: 2,
    DEBOUNCE_DELAY: 300, // milliseconds
    MAX_RESULTS: 5,
    RESULT_LIMIT: 5
  },
  
  // UI settings
  UI: {
    ANIMATION_DURATION: 200, // milliseconds
    LOADING_DELAY: 500, // show loading after delay
    ERROR_DISPLAY_DURATION: 5000, // 5 seconds
    SUCCESS_DISPLAY_DURATION: 3000 // 3 seconds
  },
  
  // Default locations for fallback
  DEFAULT_LOCATIONS: [
    { name: 'New York', country: 'US', lat: 40.7128, lon: -74.0060 },
    { name: 'London', country: 'GB', lat: 51.5074, lon: -0.1278 },
    { name: 'Tokyo', country: 'JP', lat: 35.6762, lon: 139.6503 },
    { name: 'Sydney', country: 'AU', lat: -33.8688, lon: 151.2093 },
    { name: 'Paris', country: 'FR', lat: 48.8566, lon: 2.3522 }
  ]
};

// Weather condition mappings
export const WEATHER_CONDITIONS = {
  // OpenWeatherMap condition codes to icons
  ICON_MAPPING: {
    '01d': 'clear-day',
    '01n': 'clear-night',
    '02d': 'partly-cloudy-day',
    '02n': 'partly-cloudy-night',
    '03d': 'cloudy',
    '03n': 'cloudy',
    '04d': 'overcast',
    '04n': 'overcast',
    '09d': 'drizzle',
    '09n': 'drizzle',
    '10d': 'rain',
    '10n': 'rain',
    '11d': 'thunderstorm',
    '11n': 'thunderstorm',
    '13d': 'snow',
    '13n': 'snow',
    '50d': 'fog',
    '50n': 'fog'
  },
  
  // Condition descriptions
  DESCRIPTIONS: {
    200: 'Thunderstorm with light rain',
    201: 'Thunderstorm with rain',
    202: 'Thunderstorm with heavy rain',
    210: 'Light thunderstorm',
    211: 'Thunderstorm',
    212: 'Heavy thunderstorm',
    221: 'Ragged thunderstorm',
    230: 'Thunderstorm with light drizzle',
    231: 'Thunderstorm with drizzle',
    232: 'Thunderstorm with heavy drizzle',
    
    300: 'Light intensity drizzle',
    301: 'Drizzle',
    302: 'Heavy intensity drizzle',
    310: 'Light intensity drizzle rain',
    311: 'Drizzle rain',
    312: 'Heavy intensity drizzle rain',
    313: 'Shower rain and drizzle',
    314: 'Heavy shower rain and drizzle',
    321: 'Shower drizzle',
    
    500: 'Light rain',
    501: 'Moderate rain',
    502: 'Heavy intensity rain',
    503: 'Very heavy rain',
    504: 'Extreme rain',
    511: 'Freezing rain',
    520: 'Light intensity shower rain',
    521: 'Shower rain',
    522: 'Heavy intensity shower rain',
    531: 'Ragged shower rain',
    
    600: 'Light snow',
    601: 'Snow',
    602: 'Heavy snow',
    611: 'Sleet',
    612: 'Light shower sleet',
    613: 'Shower sleet',
    615: 'Light rain and snow',
    616: 'Rain and snow',
    620: 'Light shower snow',
    621: 'Shower snow',
    622: 'Heavy shower snow',
    
    701: 'Mist',
    711: 'Smoke',
    721: 'Haze',
    731: 'Sand/dust whirls',
    741: 'Fog',
    751: 'Sand',
    761: 'Dust',
    762: 'Volcanic ash',
    771: 'Squalls',
    781: 'Tornado',
    
    800: 'Clear sky',
    801: 'Few clouds',
    802: 'Scattered clouds',
    803: 'Broken clouds',
    804: 'Overcast clouds'
  }
};

// Error messages
export const ERROR_MESSAGES = {
  NETWORK: {
    OFFLINE: 'You appear to be offline. Please check your connection.',
    TIMEOUT: 'Request timed out. Please try again.',
    SERVER_ERROR: 'Server error. Please try again later.',
    NOT_FOUND: 'Location not found. Please try a different search term.',
    RATE_LIMIT: 'Too many requests. Please wait a moment and try again.',
    INVALID_KEY: 'Invalid API key. Please contact support.',
    GENERIC: 'Network error occurred. Please try again.'
  },
  
  GEOLOCATION: {
    DENIED: 'Location access denied. Please search for a city manually.',
    UNAVAILABLE: 'Location service unavailable. Please search manually.',
    TIMEOUT: 'Location request timed out. Please try again.',
    GENERIC: 'Unable to get your location. Please search manually.'
  },
  
  DATA: {
    INVALID_RESPONSE: 'Invalid weather data received. Please try again.',
    PARSE_ERROR: 'Error processing weather data. Please try again.',
    MISSING_DATA: 'Weather data is incomplete. Please try again.',
    VALIDATION_ERROR: 'Invalid data format received.'
  },
  
  SEARCH: {
    NO_RESULTS: 'No locations found. Please try a different search term.',
    INVALID_QUERY: 'Please enter a valid city name.',
    MIN_LENGTH: 'Please enter at least 2 characters to search.'
  },
  
  CACHE: {
    STORAGE_FULL: 'Storage is full. Some data may not be saved.',
    STORAGE_ERROR: 'Error accessing local storage.',
    INVALID_CACHE: 'Cached data is invalid and has been cleared.'
  }
};

// Storage keys
export const STORAGE_KEYS = {
  WEATHER_CACHE: 'weather_app_cache',
  USER_PREFERENCES: 'weather_app_preferences',
  FAVORITE_LOCATIONS: 'weather_app_favorites',
  LAST_LOCATION: 'weather_app_last_location',
  THEME_PREFERENCE: 'weather_app_theme',
  UNITS_PREFERENCE: 'weather_app_units'
};

// Environment detection
export const ENVIRONMENT = {
  IS_DEVELOPMENT: window.location.hostname === 'localhost' || 
                  window.location.hostname === '127.0.0.1' ||
                  window.location.hostname === '',
  IS_MOBILE: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent),
  SUPPORTS_GEOLOCATION: 'geolocation' in navigator,
  SUPPORTS_LOCAL_STORAGE: (() => {
    try {
      const test = 'test';
      localStorage.setItem(test, test);
      localStorage.removeItem(test);
      return true;
    } catch (e) {
      return false;
    }
  })(),
  SUPPORTS_SERVICE_WORKER: 'serviceWorker' in navigator
};

// Feature flags
export const FEATURES = {
  ENABLE_CACHING: true,
  ENABLE_GEOLOCATION: ENVIRONMENT.SUPPORTS_GEOLOCATION,
  ENABLE_LOCAL_STORAGE: ENVIRONMENT.SUPPORTS_LOCAL_STORAGE,
  ENABLE_OFFLINE_MODE: false, // For future PWA implementation
  ENABLE_PUSH_NOTIFICATIONS: false, // For future implementation
  ENABLE_ANALYTICS: false,
  DEBUG_MODE: ENVIRONMENT.IS_DEVELOPMENT
};

// Performance monitoring
export const PERFORMANCE = {
  ENABLE_MONITORING: ENVIRONMENT.IS_DEVELOPMENT,
  LOG_API_CALLS: ENVIRONMENT.IS_DEVELOPMENT,
  LOG_CACHE_HITS: ENVIRONMENT.IS_DEVELOPMENT,
  LOG_ERRORS: true
};

// Export all configurations as default
export default {
  WEATHER_API,
  APP_CONFIG,
  WEATHER_CONDITIONS,
  ERROR_MESSAGES,
  STORAGE_KEYS,
  ENVIRONMENT,
  FEATURES,
  PERFORMANCE
};