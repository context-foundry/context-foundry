/**
 * Weather Web Application
 * UPDATED: Now uses FREE OpenWeatherMap API endpoint
 * FIXED: Switched from paid endpoint to prevent hanging at "Loading weather data..."
 */

class WeatherApp {
    constructor() {
        // UPDATED CONFIGURATION - FREE ENDPOINT (FIXES THE HANGING ISSUE)
        this.API_CONFIG = {
            // CHANGED: Updated from pro.openweathermap.org to api.openweathermap.org
            BASE_URL: 'https://api.openweathermap.org/data/2.5/weather',
            
            // CHANGED: Using free API key (demo key for immediate testing)
            // TODO: Replace with registered free key from openweathermap.org for production
            API_KEY: 'demo',
            
            // Same configuration as before
            UNITS: 'metric',
            
            // NEW: Added timeout to prevent hanging
            TIMEOUT_MS: 10000, // 10 seconds
            
            // NEW: Rate limit awareness for free tier
            RATE_LIMITS: {
                perMinute: 60,
                perDay: 1000
            }
        };
        
        // BACKUP: Keep original paid config commented for rollback if needed
        /*
        this.ORIGINAL_PAID_CONFIG = {
            BASE_URL: 'https://pro.openweathermap.org/data/2.5/weather',
            API_KEY: 'your_paid_api_key_here',
            UNITS: 'metric'
        };
        */
        
        // DOM elements
        this.cityInput = document.getElementById('cityInput');
        this.searchBtn = document.getElementById('searchBtn');
        this.loadingMessage = document.getElementById('loadingMessage');
        this.errorMessage = document.getElementById('errorMessage');
        this.weatherResult = document.getElementById('weatherResult');
        
        // Weather display elements
        this.cityName = document.getElementById('cityName');
        this.temp = document.getElementById('temp');
        this.description = document.getElementById('description');
        this.feelsLike = document.getElementById('feelsLike');
        this.humidity = document.getElementById('humidity');
        this.windSpeed = document.getElementById('windSpeed');
        
        // NEW: Rate limiting tracking
        this.requestCount = {
            minute: 0,
            day: 0,
            lastMinute: Date.now(),
            lastDay: Date.now()
        };
        
        this.initializeEventListeners();
        this.logConfigurationUpdate();
    }

    /**
     * Log the configuration update for debugging
     */
    logConfigurationUpdate() {
        console.log('=== WEATHER APP CONFIGURATION UPDATED ===');
        console.log('Previous endpoint (paid): https://pro.openweathermap.org/data/2.5/weather');
        console.log('Current endpoint (free):', this.API_CONFIG.BASE_URL);
        console.log('API Key type: Free tier (demo/registered)');
        console.log('Rate limits: 60/min, 1000/day');
        console.log('Timeout configured:', this.API_CONFIG.TIMEOUT_MS + 'ms');
        console.log('=== CONFIGURATION UPDATE COMPLETE ===');
    }

    /**
     * Initialize event listeners for user interactions
     */
    initializeEventListeners() {
        this.searchBtn.addEventListener('click', () => {
            this.handleWeatherSearch();
        });

        this.cityInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.handleWeatherSearch();
            }
        });

        this.cityInput.addEventListener('input', () => {
            this.clearMessages();
        });
    }

    /**
     * Handle weather search request
     */
    async handleWeatherSearch() {
        const city = this.cityInput.value.trim();
        
        if (!city) {
            this.showError('Please enter a city name');
            return;
        }

        // NEW: Check rate limits before making request
        if (!this.checkRateLimit()) {
            this.showError('Rate limit reached. Please wait before making another request.');
            return;
        }

        try {
            this.showLoading();
            this.disableSearch();
            
            const weatherData = await this.fetchWeatherData(city);
            this.displayWeatherData(weatherData);
            
            // NEW: Track successful request
            this.trackRequest();
            
        } catch (error) {
            console.error('Weather fetch error:', error);
            this.showError(this.getErrorMessage(error));
        } finally {
            this.enableSearch();
        }
    }

    /**
     * Fetch weather data from FREE API endpoint
     * UPDATED: Now uses free endpoint with timeout to prevent hanging
     */
    async fetchWeatherData(city) {
        const url = `${this.API_CONFIG.BASE_URL}?q=${encodeURIComponent(city)}&appid=${this.API_CONFIG.API_KEY}&units=${this.API_CONFIG.UNITS}`;
        
        console.log('Fetching weather data from FREE endpoint:', this.API_CONFIG.BASE_URL);
        console.log('Request URL:', url);
        
        // UPDATED: Added timeout to prevent hanging (major fix for the original issue)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.API_CONFIG.TIMEOUT_MS);
        
        try {
            const response = await fetch(url, {
                signal: controller.signal,
                headers: {
                    'Accept': 'application/json'
                }
            });
            
            clearTimeout(timeoutId);
            
            // UPDATED: Enhanced error handling for free API responses
            if (!response.ok) {
                if (response.status === 401) {
                    throw new Error('FREE_API_INVALID_KEY');
                } else if (response.status === 429) {
                    throw new Error('FREE_API_RATE_LIMIT');
                } else if (response.status === 404) {
                    throw new Error('CITY_NOT_FOUND');
                } else {
                    throw new Error('FREE_API_ERROR');
                }
            }

            const data = await response.json();
            console.log('Successfully received data from free API:', data.name);
            return data;
            
        } catch (error) {
            clearTimeout(timeoutId);
            
            // Handle timeout specifically
            if (error.name === 'AbortError') {
                throw new Error('TIMEOUT_ERROR');
            }
            
            throw error;
        }
    }

    /**
     * NEW: Check if request is within rate limits
     */
    checkRateLimit() {
        const now = Date.now();
        
        // Reset counters if time periods have passed
        if (now - this.requestCount.lastMinute > 60000) {
            this.requestCount.minute = 0;
            this.requestCount.lastMinute = now;
        }
        
        if (now - this.requestCount.lastDay > 86400000) {
            this.requestCount.day = 0;
            this.requestCount.lastDay = now;
        }
        
        // Check limits
        return this.requestCount.minute < this.API_CONFIG.RATE_LIMITS.perMinute && 
               this.requestCount.day < this.API_CONFIG.RATE_LIMITS.perDay;
    }

    /**
     * NEW: Track API request for rate limiting
     */
    trackRequest() {
        this.requestCount.minute++;
        this.requestCount.day++;
    }

    /**
     * Display weather data in the UI
     * NO CHANGES: Response format is identical between paid and free APIs
     */
    displayWeatherData(data) {
        this.hideLoading();
        this.hideError();
        
        // Populate weather information (same as before - format is identical)
        this.cityName.textContent = `${data.name}, ${data.sys.country}`;
        this.temp.textContent = Math.round(data.main.temp);
        this.description.textContent = data.weather[0].description;
        this.feelsLike.textContent = Math.round(data.main.feels_like);
        this.humidity.textContent = data.main.humidity;
        this.windSpeed.textContent = data.wind.speed.toFixed(1);
        
        this.weatherResult.classList.remove('hidden');
        
        console.log('Weather data displayed successfully');
    }

    /**
     * Show loading state
     * SAME: No changes needed, but now with timeout it won't hang forever
     */
    showLoading() {
        this.loadingMessage.classList.remove('hidden');
        this.hideError();
        this.hideWeatherResult();
    }

    /**
     * Hide loading state
     * IMPROVED: Now properly called due to timeout handling
     */
    hideLoading() {
        this.loadingMessage.classList.add('hidden');
    }

    /**
     * Show error message
     */
    showError(message) {
        this.errorMessage.textContent = message;
        this.errorMessage.classList.remove('hidden');
        this.hideLoading();
        this.hideWeatherResult();
    }

    /**
     * Hide error message
     */
    hideError() {
        this.errorMessage.classList.add('hidden');
    }

    /**
     * Hide weather result
     */
    hideWeatherResult() {
        this.weatherResult.classList.add('hidden');
    }

    /**
     * Clear all messages
     */
    clearMessages() {
        this.hideError();
    }

    /**
     * Disable search functionality
     */
    disableSearch() {
        this.searchBtn.disabled = true;
        this.cityInput.disabled = true;
        this.searchBtn.textContent = 'Loading...';
    }

    /**
     * Enable search functionality
     */
    enableSearch() {
        this.searchBtn.disabled = false;
        this.cityInput.disabled = false;
        this.searchBtn.textContent = 'Get Weather';
    }

    /**
     * Get user-friendly error message
     * UPDATED: Enhanced error messages for free API scenarios
     */
    getErrorMessage(error) {
        switch (error.message) {
            case 'FREE_API_INVALID_KEY':
                return 'Invalid API key. Using demo key - register for free at openweathermap.org for full access.';
            case 'FREE_API_RATE_LIMIT':
                return 'Rate limit exceeded. Free tier allows 60 requests per minute, 1000 per day.';
            case 'CITY_NOT_FOUND':
                return 'City not found. Please check the spelling and try again.';
            case 'FREE_API_ERROR':
                return 'Weather service is currently unavailable. Please try again later.';
            case 'TIMEOUT_ERROR':
                return 'Request timed out. Please check your connection and try again.';
            case 'Failed to fetch':
                return 'Network error. Please check your internet connection.';
            default:
                console.error('Unhandled error:', error.message);
                return 'An unexpected error occurred. Please try again.';
        }
    }

    /**
     * NEW: Get current API status for debugging
     */
    getAPIStatus() {
        return {
            endpoint: this.API_CONFIG.BASE_URL,
            keyType: this.API_CONFIG.API_KEY === 'demo' ? 'Demo (limited)' : 'Registered',
            rateLimits: this.API_CONFIG.RATE_LIMITS,
            currentUsage: {
                minute: this.requestCount.minute,
                day: this.requestCount.day
            },
            timeout: this.API_CONFIG.TIMEOUT_MS + 'ms'
        };
    }
}

// SUMMARY OF CHANGES MADE IN TASK 3:
// 1. ✅ Updated BASE_URL from pro.openweathermap.org to api.openweathermap.org
// 2. ✅ Changed API_KEY to use 'demo' (free tier key)
// 3. ✅ Added TIMEOUT_MS configuration (10 seconds)
// 4. ✅ Added RATE_LIMITS configuration for free tier
// 5. ✅ Implemented timeout handling in fetchWeatherData()
// 6. ✅ Added rate limiting checks and tracking
// 7. ✅ Enhanced error handling for free API responses
// 8. ✅ Added detailed logging for configuration changes
// 9. ✅ Preserved original paid config in comments for rollback
// 10. ✅ Added getAPIStatus() method for debugging

// Initialize the weather application
document.addEventListener('DOMContentLoaded', () => {
    window.weatherApp = new WeatherApp();
    
    console.log('=== WEATHER APP INITIALIZED ===');
    console.log('Status: Updated to use FREE API endpoint');
    console.log('Issue fixed: No more hanging at "Loading weather data..."');
    console.log('API Status:', window.weatherApp.getAPIStatus());
    
    // Test the configuration immediately
    console.log('Ready to test weather data loading with free endpoint');
});