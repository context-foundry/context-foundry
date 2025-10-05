/**
 * Configuration module for Weather Dashboard
 * Manages API keys, endpoints, and application settings
 */

/**
 * Weather Dashboard Configuration
 * @typedef {Object} WeatherConfig
 * @property {string} API_KEY - OpenWeatherMap API key
 * @property {string} API_BASE_URL - Base URL for OpenWeatherMap API
 * @property {number} CACHE_DURATION - Cache duration in milliseconds
 * @property {boolean} isDevelopment - Development mode flag
 * @property {Function} getApiKey - Method to retrieve API key safely
 */

// Development/Production environment detection
const isDevelopment = location.hostname === 'localhost' || 
                     location.hostname === '127.0.0.1' || 
                     location.hostname.includes('file://');

/**
 * Application configuration object
 * @type {WeatherConfig}
 */
const config = {
    // OpenWeatherMap API configuration
    API_KEY: isDevelopment 
        ? 'your-development-api-key-here' 
        : (window.WEATHER_API_KEY || 'your-production-api-key-here'),
    
    API_BASE_URL: 'https://api.openweathermap.org/data/2.5',
    
    // Cache settings (10 minutes)
    CACHE_DURATION: 10 * 60 * 1000,
    
    // Rate limiting settings
    MAX_REQUESTS_PER_MINUTE: 50,
    REQUEST_INTERVAL: 1200, // Minimum ms between requests
    
    // Environment
    isDevelopment,
    
    // Supported units
    TEMPERATURE_UNITS: {
        CELSIUS: 'C',
        FAHRENHEIT: 'F'
    },
    
    // Default settings
    DEFAULT_CITY: 'London',
    DEFAULT_UNITS: 'metric', // metric, imperial, kelvin
    
    // Icon settings
    ICON_BASE_URL: 'https://openweathermap.org/img/wn',
    ICON_SIZE: '2x', // 1x, 2x, 4x
    
    /**
     * Safely retrieve API key
     * @returns {string} API key for OpenWeatherMap
     * @throws {Error} If API key is not configured
     */
    getApiKey() {
        if (!this.API_KEY || this.API_KEY.includes('your-') || this.API_KEY === '') {
            if (isDevelopment) {
                console.warn('⚠️  No API key configured. Using demo mode.');
                return 'demo-key'; // Allow development without real key
            }
            throw new Error('OpenWeatherMap API key is not configured. Please set your API key.');
        }
        return this.API_KEY;
    },
    
    /**
     * Get full weather icon URL
     * @param {string} iconCode - Weather icon code from API
     * @returns {string} Full URL to weather icon
     */
    getIconUrl(iconCode) {
        return `${this.ICON_BASE_URL}/${iconCode}@${this.ICON_SIZE}.png`;
    },
    
    /**
     * Validate configuration
     * @throws {Error} If configuration is invalid
     */
    validate() {
        if (!this.API_BASE_URL) {
            throw new Error('API_BASE_URL is required');
        }
        
        if (typeof this.CACHE_DURATION !== 'number' || this.CACHE_DURATION < 0) {
            throw new Error('CACHE_DURATION must be a positive number');
        }
        
        if (typeof this.MAX_REQUESTS_PER_MINUTE !== 'number' || this.MAX_REQUESTS_PER_MINUTE <= 0) {
            throw new Error('MAX_REQUESTS_PER_MINUTE must be a positive number');
        }
    }
};

// Validate configuration on load
try {
    config.validate();
} catch (error) {
    console.error('Configuration validation failed:', error.message);
    if (!isDevelopment) {
        throw error;
    }
}

// Export configuration
export default config;

// Named export for compatibility
export { config };