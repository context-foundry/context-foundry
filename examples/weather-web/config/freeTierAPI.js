/**
 * Free Tier Weather API Configuration
 * Documentation: https://www.weatherapi.com/docs/
 * Free Tier Limitations and Requirements
 */

// Free tier base configuration
export const FREE_TIER_CONFIG = {
  // Free tier endpoint (no /premium path)
  baseUrl: 'https://api.weatherapi.com/v1',
  tier: 'free',
  
  // Available features in free tier
  availableFeatures: [
    'current',      // Current weather - FREE
    'forecast',     // 3-day forecast - FREE  
    'search',       // Location search - FREE
    'astronomy'     // Sun/moon data - FREE
  ],
  
  // Features NOT available in free tier
  restrictedFeatures: [
    'air_quality',    // Premium only
    'alerts',         // Premium only
    'history',        // Limited to 7 days, premium for more
    'sports',         // Premium only
    'future',         // Premium only (beyond 3 days)
    'marine'          // Premium only
  ],
  
  // Free tier limits
  limits: {
    requestsPerMonth: 1000000,    // 1M requests/month
    requestsPerDay: null,         // No daily limit specified
    requestsPerSecond: 3,         // Rate limiting
    forecastDays: 3,              // Maximum 3 days forecast
    historyDays: 7,               // Only 7 days history
    locationsPerSearch: 10        // Max search results
  },
  
  // Free tier request parameters
  allowedParameters: {
    // Required
    key: 'string',                // API key (required)
    q: 'string',                  // Location (required)
    
    // Optional - Current Weather
    aqi: 'no',                    // Air quality NOT available in free
    lang: 'string',               // Language code
    
    // Optional - Forecast  
    days: 'number',               // 1-3 only for free tier
    dt: 'string',                 // Specific date (within limits)
    unixdt: 'number',             // Unix timestamp
    hour: 'number',               // Specific hour (0-23)
    
    // Optional - History (limited)
    end_dt: 'string',             // End date (max 7 days back)
    unixend_dt: 'number'          // Unix end timestamp
  },
  
  // Request configuration for free tier
  requestConfig: {
    timeout: 10000,               // 10 second timeout
    retries: 3,                   // Max retries
    retryDelay: 1000,             // 1 second between retries
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'weather-web-app/1.0'
    }
  }
};

// Free tier API endpoints
export const FREE_TIER_ENDPOINTS = {
  // Current weather
  current: '/current.json',
  
  // Forecast (max 3 days)  
  forecast: '/forecast.json',
  
  // Location search
  search: '/search.json',
  
  // Astronomy data
  astronomy: '/astronomy.json',
  
  // History (limited to 7 days)
  history: '/history.json',
  
  // Time zone
  timezone: '/timezone.json'
};

// Free tier response structure (what to expect)
export const FREE_TIER_RESPONSE_STRUCTURE = {
  current: {
    location: {
      name: 'string',
      region: 'string', 
      country: 'string',
      lat: 'number',
      lon: 'number',
      tz_id: 'string',
      localtime_epoch: 'number',
      localtime: 'string'
    },
    current: {
      last_updated_epoch: 'number',
      last_updated: 'string',
      temp_c: 'number',
      temp_f: 'number',
      is_day: 'number',
      condition: {
        text: 'string',
        icon: 'string',
        code: 'number'
      },
      wind_mph: 'number',
      wind_kph: 'number', 
      wind_degree: 'number',
      wind_dir: 'string',
      pressure_mb: 'number',
      pressure_in: 'number',
      precip_mm: 'number',
      precip_in: 'number',
      humidity: 'number',
      cloud: 'number',
      feelslike_c: 'number',
      feelslike_f: 'number',
      vis_km: 'number',
      vis_miles: 'number',
      uv: 'number',
      gust_mph: 'number',
      gust_kph: 'number'
      // NOTE: air_quality field NOT available in free tier
    }
    // NOTE: alerts field NOT available in free tier
  },
  
  forecast: {
    // Same location structure as above
    location: 'object',
    current: 'object',
    forecast: {
      forecastday: [
        {
          date: 'string',
          date_epoch: 'number',
          day: {
            maxtemp_c: 'number',
            maxtemp_f: 'number',
            mintemp_c: 'number', 
            mintemp_f: 'number',
            avgtemp_c: 'number',
            avgtemp_f: 'number',
            maxwind_mph: 'number',
            maxwind_kph: 'number',
            totalprecip_mm: 'number',
            totalprecip_in: 'number',
            avgvis_km: 'number',
            avgvis_miles: 'number',
            avghumidity: 'number',
            daily_will_it_rain: 'number',
            daily_chance_of_rain: 'number',
            daily_will_it_snow: 'number',
            daily_chance_of_snow: 'number',
            condition: {
              text: 'string',
              icon: 'string',
              code: 'number'
            },
            uv: 'number'
          },
          astro: {
            sunrise: 'string',
            sunset: 'string',
            moonrise: 'string',
            moonset: 'string',
            moon_phase: 'string',
            moon_illumination: 'string'
          },
          hour: [
            {
              time_epoch: 'number',
              time: 'string',
              temp_c: 'number',
              temp_f: 'number',
              is_day: 'number',
              condition: 'object',
              wind_mph: 'number',
              wind_kph: 'number',
              wind_degree: 'number',
              wind_dir: 'string',
              pressure_mb: 'number',
              pressure_in: 'number',
              precip_mm: 'number',
              precip_in: 'number',
              humidity: 'number',
              cloud: 'number',
              feelslike_c: 'number',
              feelslike_f: 'number',
              windchill_c: 'number',
              windchill_f: 'number',
              heatindex_c: 'number',
              heatindex_f: 'number',
              dewpoint_c: 'number',
              dewpoint_f: 'number',
              will_it_rain: 'number',
              chance_of_rain: 'number',
              will_it_snow: 'number',
              chance_of_snow: 'number',
              vis_km: 'number',
              vis_miles: 'number',
              gust_mph: 'number',
              gust_kph: 'number',
              uv: 'number'
            }
          ]
        }
      ]
    }
  }
};

// Error codes specific to free tier
export const FREE_TIER_ERROR_CODES = {
  // API Key errors
  1002: 'API key not provided',
  1003: 'Parameter q not provided',
  1005: 'API request url is invalid',
  1006: 'No location found matching parameter q',
  
  // Rate limiting (common in free tier)
  1008: 'API key has been disabled',
  1009: 'API key does not have access to the resource',
  
  // Free tier specific limits
  9000: 'JSON body passed in bulk request is invalid',
  9001: 'JSON body contains too many locations for bulk request',
  9999: 'Internal application error'
};

// Free tier request examples
export const FREE_TIER_REQUEST_EXAMPLES = {
  // Current weather
  current: {
    url: 'https://api.weatherapi.com/v1/current.json',
    params: {
      key: 'YOUR_API_KEY',
      q: 'London',
      aqi: 'no'  // Must be 'no' for free tier
    }
  },
  
  // 3-day forecast  
  forecast: {
    url: 'https://api.weatherapi.com/v1/forecast.json',
    params: {
      key: 'YOUR_API_KEY',
      q: 'New York',
      days: 3,      // Maximum 3 for free tier
      aqi: 'no',    // Must be 'no' for free tier
      alerts: 'no'  // Must be 'no' for free tier
    }
  },
  
  // Location search
  search: {
    url: 'https://api.weatherapi.com/v1/search.json',
    params: {
      key: 'YOUR_API_KEY',
      q: 'Paris'
    }
  },
  
  // History (limited)
  history: {
    url: 'https://api.weatherapi.com/v1/history.json', 
    params: {
      key: 'YOUR_API_KEY',
      q: 'Tokyo',
      dt: '2023-12-01'  // Must be within last 7 days for free
    }
  }
};

// Free tier best practices
export const FREE_TIER_BEST_PRACTICES = {
  caching: {
    current: 300000,        // 5 minutes - reasonable for free tier
    forecast: 3600000,      // 1 hour - conserve API calls  
    search: 86400000,       // 24 hours - location data rarely changes
    history: 86400000       // 24 hours - historical data doesn't change
  },
  
  rateLimiting: {
    requestsPerSecond: 2,   // Stay under 3/second limit
    burstLimit: 5,          // Allow small bursts
    queueEnabled: true      // Queue requests if over limit
  },
  
  errorHandling: {
    retryOn: [429, 500, 502, 503, 504],  // Retry on these codes
    maxRetries: 3,
    backoffMultiplier: 2,
    initialDelayMs: 1000
  },
  
  optimization: {
    batchRequests: false,     // Not available in free tier
    compression: true,        // Enable gzip
    keepAlive: true,         // Reuse connections
    timeout: 10000           // 10 second timeout
  }
};

export default FREE_TIER_CONFIG;