/**
 * Free API Configuration Template
 * Ready-to-use configuration for free OpenWeatherMap API
 */

/**
 * FREE API CONFIGURATION - READY FOR IMPLEMENTATION
 * This will replace the paid configuration in Task 3
 */
const FREE_API_CONFIG = {
    // Free OpenWeatherMap API endpoint (replaces paid pro.openweathermap.org)
    BASE_URL: 'https://api.openweathermap.org/data/2.5/weather',
    
    // Free API key options (choose one for implementation)
    API_KEY_OPTIONS: {
        // Option 1: Demo key (limited functionality, good for testing)
        demo: 'demo',
        
        // Option 2: Free registered key (recommended for production)
        // Register at: https://openweathermap.org/api
        registered: 'YOUR_FREE_API_KEY_HERE',
        
        // Option 3: Sample working key format
        sample: 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6'
    },
    
    // API parameters
    UNITS: 'metric', // metric, imperial, kelvin
    LANGUAGE: 'en',  // en, es, fr, de, etc.
    
    // Free tier limitations
    RATE_LIMITS: {
        perMinute: 60,      // 60 calls per minute
        perDay: 1000,       // 1,000 calls per day
        perMonth: 30000     // ~30,000 calls per month
    },
    
    // Request timeout (important for free tier)
    TIMEOUT_MS: 10000,      // 10 seconds
    
    // Retry configuration for rate limiting
    RETRY_CONFIG: {
        maxRetries: 3,
        backoffMs: 1000,    // Start with 1 second
        backoffMultiplier: 2 // Double each retry
    }
};

/**
 * FREE API REQUEST BUILDER
 * Builds properly formatted requests for free API
 */
class FreeAPIRequestBuilder {
    constructor(config = FREE_API_CONFIG) {
        this.config = config;
    }
    
    /**
     * Build weather request URL for free API
     */
    buildWeatherURL(city, apiKey = null) {
        const key = apiKey || this.config.API_KEY_OPTIONS.registered;
        const params = new URLSearchParams({
            q: city,
            appid: key,
            units: this.config.UNITS,
            lang: this.config.LANGUAGE
        });
        
        return `${this.config.BASE_URL}?${params.toString()}`;
    }
    
    /**
     * Create fetch options with timeout for free API
     */
    createFetchOptions() {
        return {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'User-Agent': 'WeatherWeb/1.0'
            },
            // Timeout handling
            signal: AbortSignal.timeout(this.config.TIMEOUT_MS)
        };
    }
    
    /**
     * Validate API response from free endpoint
     */
    validateResponse(response) {
        if (!response.ok) {
            switch (response.status) {
                case 401:
                    throw new Error('FREE_API_INVALID_KEY');
                case 429:
                    throw new Error('FREE_API_RATE_LIMIT');
                case 404:
                    throw new Error('CITY_NOT_FOUND');
                default:
                    throw new Error('FREE_API_ERROR');
            }
        }
        return response;
    }
}

/**
 * FREE API ERROR MESSAGES
 * User-friendly messages for free API specific errors
 */
const FREE_API_ERROR_MESSAGES = {
    'FREE_API_INVALID_KEY': 'Invalid API key. Please check your free API key from openweathermap.org',
    'FREE_API_RATE_LIMIT': 'Rate limit exceeded. Free tier allows 60 requests per minute.',
    'FREE_API_ERROR': 'Weather service temporarily unavailable. Please try again.',
    'CITY_NOT_FOUND': 'City not found. Please check spelling and try again.',
    'NETWORK_ERROR': 'Network connection error. Please check your internet connection.',
    'TIMEOUT_ERROR': 'Request timed out. Please try again.'
};

/**
 * SAMPLE USAGE FOR TASK 3 IMPLEMENTATION
 */
const IMPLEMENTATION_EXAMPLE = {
    // How to use in weather.js (Task 3)
    usage: `
    // Replace current API_CONFIG with:
    this.API_CONFIG = {
        BASE_URL: '${FREE_API_CONFIG.BASE_URL}',
        API_KEY: '${FREE_API_CONFIG.API_KEY_OPTIONS.registered}',
        UNITS: '${FREE_API_CONFIG.UNITS}',
        TIMEOUT_MS: ${FREE_API_CONFIG.TIMEOUT_MS}
    };
    
    // Update fetchWeatherData method to use timeout:
    const response = await fetch(url, {
        signal: AbortSignal.timeout(this.API_CONFIG.TIMEOUT_MS)
    });
    `,
    
    testURL: function(city = 'London', apiKey = 'demo') {
        return `${FREE_API_CONFIG.BASE_URL}?q=${city}&appid=${apiKey}&units=${FREE_API_CONFIG.UNITS}`;
    }
};

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        FREE_API_CONFIG,
        FreeAPIRequestBuilder,
        FREE_API_ERROR_MESSAGES,
        IMPLEMENTATION_EXAMPLE
    };
}

console.log('Free API Configuration Ready');
console.log('Test URL example:', IMPLEMENTATION_EXAMPLE.testURL());