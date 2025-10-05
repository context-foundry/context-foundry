/**
 * Weather API Client
 * Handles all interactions with OpenWeatherMap API
 * Provides clean abstraction layer with error handling, caching, and retry logic
 */

class WeatherAPIClient {
    constructor(config) {
        this.config = config || window.weatherConfig;
        this.cache = new Map();
        this.requestQueue = new Map();
        this.rateLimiter = {
            requests: [],
            maxRequests: 60,
            timeWindow: 60000 // 1 minute
        };
        
        // Request timeout settings
        this.timeoutDuration = 10000; // 10 seconds
        this.retryAttempts = 3;
        this.retryDelay = 1000; // 1 second base delay
        
        // Cache settings
        this.cacheTimeout = 300000; // 5 minutes
        this.maxCacheSize = 50;
    }

    /**
     * Get current weather for a city
     * @param {string} city - City name
     * @param {Object} options - Additional options
     * @returns {Promise<Object>} Weather data
     */
    async getCurrentWeather(city, options = {}) {
        if (!city || typeof city !== 'string') {
            throw new WeatherAPIError('City name is required and must be a string', 'INVALID_INPUT');
        }

        const normalizedCity = this.normalizeCity(city);
        const cacheKey = `current_${normalizedCity}`;

        // Check cache first (unless forced refresh)
        if (!options.forceRefresh) {
            const cachedData = this.getCachedData(cacheKey);
            if (cachedData) {
                console.log(`📄 Using cached weather data for ${city}`);
                return cachedData;
            }
        }

        // Check for duplicate in-flight requests
        if (this.requestQueue.has(cacheKey)) {
            console.log(`⏳ Waiting for existing request for ${city}`);
            return await this.requestQueue.get(cacheKey);
        }

        // Create new request promise
        const requestPromise = this.executeWeatherRequest(normalizedCity, options);
        this.requestQueue.set(cacheKey, requestPromise);

        try {
            const result = await requestPromise;
            this.setCachedData(cacheKey, result);
            return result;
        } finally {
            this.requestQueue.delete(cacheKey);
        }
    }

    /**
     * Execute weather API request with retry logic
     * @param {string} city - Normalized city name
     * @param {Object} options - Request options
     * @returns {Promise<Object>} Weather data
     */
    async executeWeatherRequest(city, options = {}) {
        let lastError = null;
        const maxAttempts = options.maxRetries || this.retryAttempts;

        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                // Check rate limiting
                this.checkRateLimit();

                // Build request URL
                const url = this.buildWeatherURL(city, options);
                
                console.log(`🌐 Weather API request (attempt ${attempt}/${maxAttempts}): ${this.maskUrl(url)}`);

                // Execute request with timeout
                const response = await this.fetchWithTimeout(url, {
                    method: 'GET',
                    headers: this.getRequestHeaders(),
                    signal: options.signal // Allow external cancellation
                });

                // Track successful request
                this.trackRequest(true);

                // Process response
                const data = await this.processResponse(response, city);
                
                console.log(`✅ Weather data retrieved successfully for ${city}`);
                return data;

            } catch (error) {
                lastError = error;
                console.warn(`⚠️ Weather API request failed (attempt ${attempt}/${maxAttempts}):`, error.message);

                // Track failed request
                this.trackRequest(false);

                // Don't retry on certain error types
                if (this.shouldNotRetry(error) || attempt === maxAttempts) {
                    break;
                }

                // Wait before retrying (exponential backoff)
                const delay = this.retryDelay * Math.pow(2, attempt - 1);
                await this.sleep(delay);
            }
        }

        // All attempts failed
        throw this.enhanceError(lastError, city);
    }

    /**
     * Build weather API URL
     * @param {string} city - City name
     * @param {Object} options - URL options
     * @returns {string} Complete API URL
     */
    buildWeatherURL(city, options = {}) {
        if (!this.config || !this.config.initialized) {
            throw new WeatherAPIError('Weather configuration not initialized', 'CONFIG_ERROR');
        }

        const baseUrl = this.config.baseUrl || 'https://api.openweathermap.org/data/2.5';
        const endpoint = options.endpoint || 'weather';
        
        const params = new URLSearchParams({
            q: city,
            appid: this.config.apiKey,
            units: options.units || this.config.units || 'metric',
            lang: options.language || 'en'
        });

        // Add optional parameters
        if (options.coordinates) {
            params.delete('q');
            params.set('lat', options.coordinates.lat);
            params.set('lon', options.coordinates.lon);
        }

        return `${baseUrl}/${endpoint}?${params.toString()}`;
    }

    /**
     * Get request headers
     * @returns {Object} HTTP headers
     */
    getRequestHeaders() {
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'WeatherApp/1.0'
        };
    }

    /**
     * Fetch with timeout support
     * @param {string} url - Request URL
     * @param {Object} options - Fetch options
     * @returns {Promise<Response>} Fetch response
     */
    async fetchWithTimeout(url, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeoutDuration);

        try {
            const response = await fetch(url, {
                ...options,
                signal: options.signal || controller.signal
            });
            
            clearTimeout(timeoutId);
            return response;
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new WeatherAPIError('Request timed out', 'TIMEOUT');
            }
            
            throw error;
        }
    }

    /**
     * Process API response
     * @param {Response} response - Fetch response
     * @param {string} city - City name for context
     * @returns {Promise<Object>} Processed weather data
     */
    async processResponse(response, city) {
        if (!response.ok) {
            await this.handleErrorResponse(response, city);
            return; // handleErrorResponse throws, this won't execute
        }

        let data;
        try {
            data = await response.json();
        } catch (error) {
            throw new WeatherAPIError('Invalid JSON response from weather API', 'PARSE_ERROR');
        }

        // Validate response structure
        this.validateWeatherData(data, city);

        // Transform to consistent format
        return this.transformWeatherData(data);
    }

    /**
     * Handle API error responses
     * @param {Response} response - Error response
     * @param {string} city - City name for context
     */
    async handleErrorResponse(response, city) {
        let errorData = null;
        
        try {
            errorData = await response.json();
        } catch (parseError) {
            // Can't parse error response, use status text
        }

        const errorMessage = errorData?.message || response.statusText || 'Unknown error';
        
        switch (response.status) {
            case 400:
                throw new WeatherAPIError(`Invalid request: ${errorMessage}`, 'BAD_REQUEST');
            
            case 401:
                throw new WeatherAPIError('Invalid API key. Please check your configuration.', 'UNAUTHORIZED');
            
            case 404:
                throw new WeatherAPIError(`City "${city}" not found. Please check the spelling and try again.`, 'NOT_FOUND');
            
            case 429:
                throw new WeatherAPIError('Too many requests. Please wait a moment and try again.', 'RATE_LIMITED');
            
            case 500:
            case 502:
            case 503:
            case 504:
                throw new WeatherAPIError('Weather service is temporarily unavailable. Please try again later.', 'SERVICE_ERROR');
            
            default:
                throw new WeatherAPIError(`Weather API error (${response.status}): ${errorMessage}`, 'API_ERROR');
        }
    }

    /**
     * Validate weather data structure
     * @param {Object} data - Raw API response
     * @param {string} city - City name for context
     */
    validateWeatherData(data, city) {
        const requiredFields = ['name', 'main', 'weather', 'sys'];
        const missingFields = requiredFields.filter(field => !data[field]);
        
        if (missingFields.length > 0) {
            throw new WeatherAPIError(
                `Invalid weather data received: missing fields ${missingFields.join(', ')}`,
                'INVALID_DATA'
            );
        }

        if (!Array.isArray(data.weather) || data.weather.length === 0) {
            throw new WeatherAPIError('Invalid weather data: no weather information', 'INVALID_DATA');
        }

        if (!data.main.temp || !data.main.humidity) {
            throw new WeatherAPIError('Invalid weather data: missing temperature or humidity', 'INVALID_DATA');
        }
    }

    /**
     * Transform raw API data to consistent format
     * @param {Object} rawData - Raw API response
     * @returns {Object} Transformed weather data
     */
    transformWeatherData(rawData) {
        const weather = rawData.weather[0];
        
        return {
            // Location information
            city: rawData.name,
            country: rawData.sys.country,
            coordinates: {
                lat: rawData.coord?.lat,
                lon: rawData.coord?.lon
            },
            
            // Current conditions
            temperature: Math.round(rawData.main.temp),
            feelsLike: Math.round(rawData.main.feels_like),
            tempMin: Math.round(rawData.main.temp_min),
            tempMax: Math.round(rawData.main.temp_max),
            
            // Weather description
            condition: weather.main,
            description: weather.description,
            icon: weather.icon,
            
            // Additional metrics
            humidity: rawData.main.humidity,
            pressure: rawData.main.pressure,
            visibility: rawData.visibility,
            
            // Wind information
            windSpeed: rawData.wind?.speed || 0,
            windDirection: rawData.wind?.deg || 0,
            windGust: rawData.wind?.gust,
            
            // Atmospheric conditions
            clouds: rawData.clouds?.all || 0,
            
            // Timestamps
            timestamp: new Date(),
            sunrise: rawData.sys.sunrise ? new Date(rawData.sys.sunrise * 1000) : null,
            sunset: rawData.sys.sunset ? new Date(rawData.sys.sunset * 1000) : null,
            
            // Raw data for debugging
            raw: rawData
        };
    }

    /**
     * Rate limiting check
     */
    checkRateLimit() {
        const now = Date.now();
        
        // Remove old requests outside the time window
        this.rateLimiter.requests = this.rateLimiter.requests.filter(
            timestamp => now - timestamp < this.rateLimiter.timeWindow
        );
        
        // Check if we're over the limit
        if (this.rateLimiter.requests.length >= this.rateLimiter.maxRequests) {
            throw new WeatherAPIError(
                'Rate limit exceeded. Please wait a moment and try again.',
                'RATE_LIMITED'
            );
        }
    }

    /**
     * Track API request for rate limiting
     * @param {boolean} success - Whether request was successful
     */
    trackRequest(success) {
        this.rateLimiter.requests.push(Date.now());
    }

    /**
     * Check if error should not trigger retry
     * @param {Error} error - The error to check
     * @returns {boolean} True if should not retry
     */
    shouldNotRetry(error) {
        const noRetryTypes = ['UNAUTHORIZED', 'NOT_FOUND', 'BAD_REQUEST', 'INVALID_INPUT'];
        return error instanceof WeatherAPIError && noRetryTypes.includes(error.code);
    }

    /**
     * Enhance error with additional context
     * @param {Error} error - Original error
     * @param {string} city - City name
     * @returns {Error} Enhanced error
     */
    enhanceError(error, city) {
        if (error instanceof WeatherAPIError) {
            return error;
        }

        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            return new WeatherAPIError(
                'Network connection failed. Please check your internet connection.',
                'NETWORK_ERROR'
            );
        }

        return new WeatherAPIError(
            `Failed to get weather data for ${city}: ${error.message}`,
            'UNKNOWN_ERROR'
        );
    }

    /**
     * Cache management methods
     */
    getCachedData(key) {
        const cached = this.cache.get(key);
        if (!cached) return null;

        // Check if cache is expired
        if (Date.now() - cached.timestamp > this.cacheTimeout) {
            this.cache.delete(key);
            return null;
        }

        return cached.data;
    }

    setCachedData(key, data) {
        // Clean old cache entries if at max size
        if (this.cache.size >= this.maxCacheSize) {
            const oldestKey = this.cache.keys().next().value;
            this.cache.delete(oldestKey);
        }

        this.cache.set(key, {
            data: data,
            timestamp: Date.now()
        });
    }

    clearCache() {
        this.cache.clear();
        console.log('🗑️ Weather API cache cleared');
    }

    /**
     * Utility methods
     */
    normalizeCity(city) {
        return city.trim().toLowerCase();
    }

    maskUrl(url) {
        return url.replace(/appid=[^&]+/, 'appid=***');
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Get API client status and metrics
     */
    getStatus() {
        return {
            cacheSize: this.cache.size,
            requestsInWindow: this.rateLimiter.requests.length,
            queuedRequests: this.requestQueue.size,
            initialized: !!this.config?.initialized
        };
    }

    /**
     * Get city suggestions (if supported by API)
     * @param {string} query - Search query
     * @returns {Promise<Array>} City suggestions
     */
    async getCitySuggestions(query) {
        if (!query || query.length < 2) {
            return [];
        }

        try {
            // This would use the geocoding API for suggestions
            const url = `${this.config.baseUrl.replace('data/2.5', 'geo/1.0')}/direct?q=${encodeURIComponent(query)}&limit=5&appid=${this.config.apiKey}`;
            
            const response = await this.fetchWithTimeout(url);
            if (!response.ok) return [];

            const data = await response.json();
            
            return data.map(item => ({
                name: item.name,
                country: item.country,
                state: item.state,
                lat: item.lat,
                lon: item.lon,
                displayName: `${item.name}${item.state ? `, ${item.state}` : ''}, ${item.country}`
            }));
        } catch (error) {
            console.warn('Failed to get city suggestions:', error.message);
            return [];
        }
    }
}

/**
 * Custom error class for Weather API errors
 */
class WeatherAPIError extends Error {
    constructor(message, code = 'UNKNOWN_ERROR', originalError = null) {
        super(message);
        this.name = 'WeatherAPIError';
        this.code = code;
        this.originalError = originalError;
        this.timestamp = new Date();
    }

    toJSON() {
        return {
            name: this.name,
            message: this.message,
            code: this.code,
            timestamp: this.timestamp,
            originalError: this.originalError?.message
        };
    }
}

// Create and export global API client instance
if (typeof window !== 'undefined') {
    window.WeatherAPIClient = WeatherAPIClient;
    window.WeatherAPIError = WeatherAPIError;
    
    // Initialize API client when config is available
    window.weatherAPI = new WeatherAPIClient();
}

// Export for Node.js environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { WeatherAPIClient, WeatherAPIError };
}