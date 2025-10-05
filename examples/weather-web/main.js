/**
 * Main Weather App JavaScript
 * Handles user interactions, API calls, and UI updates
 */

class WeatherApp {
    constructor() {
        // DOM Elements
        this.form = null;
        this.cityInput = null;
        this.searchButton = null;
        this.loadingState = null;
        this.weatherDisplay = null;
        this.errorDisplay = null;
        
        // Debug elements
        this.debugPanel = null;
        this.debugMetrics = {
            requestCount: 0,
            errorCount: 0,
            successCount: 0,
            totalResponseTime: 0,
            lastSuccess: null,
            cacheHits: 0
        };
        
        // State management
        this.isLoading = false;
        this.lastSearchedCity = null;
        this.cache = new Map();
        
        // Event handlers (bound to maintain 'this' context)
        this.handleFormSubmit = this.handleFormSubmit.bind(this);
        this.handleKeyPress = this.handleKeyPress.bind(this);
        this.handleRetryClick = this.handleRetryClick.bind(this);
        this.handleDebugToggle = this.handleDebugToggle.bind(this);
        this.handleDebugExport = this.handleDebugExport.bind(this);
        this.handleCacheClear = this.handleCacheClear.bind(this);
        this.handleMetricsReset = this.handleMetricsReset.bind(this);
    }

    /**
     * Initialize the application
     */
    async init() {
        console.log('🌤️ Initializing Weather App...');
        
        try {
            // Wait for DOM to be ready
            if (document.readyState === 'loading') {
                await new Promise(resolve => {
                    document.addEventListener('DOMContentLoaded', resolve);
                });
            }

            // Initialize configuration
            const configInitialized = await window.weatherConfig.init();
            if (!configInitialized) {
                console.error('Failed to initialize weather configuration');
                this.updateDebugState('configuration_error');
                return false;
            }

            // Get DOM elements
            this.initializeDOMElements();

            // Bind event listeners
            this.bindEventListeners();

            // Initialize debug panel
            this.initializeDebugPanel();

            // Update debug state
            this.updateDebugState('ready');

            console.log('✅ Weather App initialized successfully');
            return true;

        } catch (error) {
            console.error('❌ Failed to initialize Weather App:', error);
            this.updateDebugState('initialization_error');
            return false;
        }
    }

    /**
     * Get and validate DOM elements
     */
    initializeDOMElements() {
        // Main form elements
        this.form = document.getElementById('weather-form');
        this.cityInput = document.getElementById('city-input');
        this.searchButton = document.getElementById('search-button');
        
        // Display elements
        this.loadingState = document.getElementById('loading-state');
        this.weatherDisplay = document.getElementById('weather-display');
        this.errorDisplay = document.getElementById('error-display');
        
        // Debug elements
        this.debugPanel = document.getElementById('debug-panel');
        
        // Validate required elements exist
        const requiredElements = [
            'form', 'cityInput', 'searchButton', 
            'loadingState', 'weatherDisplay', 'errorDisplay'
        ];
        
        for (const elementName of requiredElements) {
            if (!this[elementName]) {
                throw new Error(`Required DOM element not found: ${elementName}`);
            }
        }

        console.log('✅ DOM elements initialized');
    }

    /**
     * Bind all event listeners
     */
    bindEventListeners() {
        // Form submission
        this.form.addEventListener('submit', this.handleFormSubmit);
        
        // Input events
        this.cityInput.addEventListener('keypress', this.handleKeyPress);
        this.cityInput.addEventListener('input', this.handleInputChange.bind(this));
        
        // Button events
        const retryButton = document.getElementById('retry-button');
        if (retryButton) {
            retryButton.addEventListener('click', this.handleRetryClick);
        }

        // Debug panel events
        const debugToggle = document.getElementById('debug-toggle');
        if (debugToggle) {
            debugToggle.addEventListener('click', this.handleDebugToggle);
        }

        const exportButton = document.getElementById('export-debug');
        if (exportButton) {
            exportButton.addEventListener('click', this.handleDebugExport);
        }

        const clearCacheButton = document.getElementById('clear-cache');
        if (clearCacheButton) {
            clearCacheButton.addEventListener('click', this.handleCacheClear);
        }

        const resetMetricsButton = document.getElementById('reset-metrics');
        if (resetMetricsButton) {
            resetMetricsButton.addEventListener('click', this.handleMetricsReset);
        }

        console.log('✅ Event listeners bound');
    }

    /**
     * Handle form submission
     */
    async handleFormSubmit(event) {
        event.preventDefault();
        
        const city = this.cityInput.value.trim();
        if (!city) {
            this.showError('Please enter a city name', 'City name is required');
            this.cityInput.focus();
            return;
        }

        if (city.length < 2) {
            this.showError('City name too short', 'Please enter at least 2 characters');
            this.cityInput.focus();
            return;
        }

        await this.searchWeather(city);
    }

    /**
     * Handle key press events
     */
    handleKeyPress(event) {
        if (event.key === 'Enter' && !this.isLoading) {
            this.form.dispatchEvent(new Event('submit'));
        }
    }

    /**
     * Handle input changes (for real-time validation)
     */
    handleInputChange(event) {
        const value = event.target.value;
        const isValid = value.length >= 2;
        
        // Update button state
        this.searchButton.disabled = !isValid || this.isLoading;
        
        // Clear previous errors when user starts typing
        if (value.length > 0) {
            this.hideError();
        }
    }

    /**
     * Handle retry button click
     */
    handleRetryClick() {
        if (this.lastSearchedCity) {
            this.searchWeather(this.lastSearchedCity);
        } else {
            this.cityInput.focus();
        }
    }

    /**
     * Search for weather data
     */
    async searchWeather(city) {
        if (this.isLoading) {
            console.warn('Search already in progress');
            return;
        }

        console.log(`🔍 Searching weather for: ${city}`);
        
        this.lastSearchedCity = city;
        this.setLoadingState(true);
        this.hideError();
        this.hideWeatherDisplay();
        
        const startTime = performance.now();
        this.updateDebugState('fetching');

        try {
            // Check cache first
            const cacheKey = city.toLowerCase();
            const cachedData = this.getCachedData(cacheKey);
            
            if (cachedData) {
                console.log('📄 Using cached data');
                this.debugMetrics.cacheHits++;
                this.displayWeatherData(cachedData);
                this.updateDebugMetrics(performance.now() - startTime, true);
                return;
            }

            // Make API request
            const weatherData = await this.fetchWeatherData(city);
            
            // Cache the result
            this.setCachedData(cacheKey, weatherData);
            
            // Display the data
            this.displayWeatherData(weatherData);
            
            // Update metrics
            this.updateDebugMetrics(performance.now() - startTime, true);
            this.updateDebugState('idle');
            
            console.log('✅ Weather data retrieved successfully');

        } catch (error) {
            console.error('❌ Failed to get weather data:', error);
            
            this.handleWeatherError(error);
            this.updateDebugMetrics(performance.now() - startTime, false);
            this.updateDebugState('error');
        } finally {
            this.setLoadingState(false);
        }
    }

    /**
     * Fetch weather data from API
     */
    async fetchWeatherData(city) {
        this.debugMetrics.requestCount++;
        
        try {
            const url = window.weatherConfig.getWeatherUrl(city);
            console.log('🌐 Making API request to:', url.replace(/appid=[^&]+/, 'appid=***'));
            
            const response = await fetch(url);
            
            if (!response.ok) {
                await this.handleAPIError(response);
                return;
            }

            const data = await response.json();
            return this.processWeatherData(data);

        } catch (error) {
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                throw new Error('Network connection failed. Please check your internet connection.');
            }
            throw error;
        }
    }

    /**
     * Handle API error responses
     */
    async handleAPIError(response) {
        let errorMessage = `API request failed with status ${response.status}`;
        
        try {
            const errorData = await response.json();
            if (errorData.message) {
                errorMessage = errorData.message;
            }
        } catch (parseError) {
            // Use default message if can't parse error response
        }

        switch (response.status) {
            case 401:
                throw new Error('Invalid API key. Please check your configuration.');
            case 404:
                throw new Error('City not found. Please check the spelling and try again.');
            case 429:
                throw new Error('Too many requests. Please wait a moment and try again.');
            case 500:
            case 502:
            case 503:
                throw new Error('Weather service is temporarily unavailable. Please try again later.');
            default:
                throw new Error(errorMessage);
        }
    }

    /**
     * Process raw weather data from API
     */
    processWeatherData(data) {
        return {
            city: data.name,
            country: data.sys.country,
            temperature: Math.round(data.main.temp),
            feelsLike: Math.round(data.main.feels_like),
            description: data.weather[0].description,
            icon: data.weather[0].icon,
            humidity: data.main.humidity,
            windSpeed: data.wind.speed,
            pressure: data.main.pressure,
            timestamp: new Date(),
            raw: data
        };
    }

    /**
     * Display weather data in UI
     */
    displayWeatherData(weatherData) {
        // Update weather display elements
        document.getElementById('weather-city').textContent = weatherData.city;
        document.getElementById('weather-country').textContent = weatherData.country;
        document.getElementById('weather-temp').textContent = weatherData.temperature;
        document.getElementById('weather-desc').textContent = 
            weatherData.description.charAt(0).toUpperCase() + weatherData.description.slice(1);
        document.getElementById('weather-icon').textContent = this.getWeatherEmoji(weatherData.icon);
        
        // Update details
        document.getElementById('weather-feels-like').textContent = `${weatherData.feelsLike}°C`;
        document.getElementById('weather-humidity').textContent = `${weatherData.humidity}%`;
        document.getElementById('weather-wind').textContent = `${weatherData.windSpeed} m/s`;
        document.getElementById('weather-pressure').textContent = `${weatherData.pressure} hPa`;
        
        // Update timestamp
        document.getElementById('weather-timestamp').textContent = 
            `Last updated: ${weatherData.timestamp.toLocaleString()}`;

        // Show weather display
        this.showWeatherDisplay();
    }

    /**
     * Get weather emoji for icon code
     */
    getWeatherEmoji(iconCode) {
        const emojiMap = {
            '01d': '☀️', '01n': '🌙',
            '02d': '⛅', '02n': '☁️',
            '03d': '☁️', '03n': '☁️',
            '04d': '☁️', '04n': '☁️',
            '09d': '🌧️', '09n': '🌧️',
            '10d': '🌦️', '10n': '🌧️',
            '11d': '⛈️', '11n': '⛈️',
            '13d': '🌨️', '13n': '🌨️',
            '50d': '🌫️', '50n': '🌫️'
        };
        return emojiMap[iconCode] || '🌤️';
    }

    /**
     * Handle weather-related errors
     */
    handleWeatherError(error) {
        this.debugMetrics.errorCount++;
        
        let title = 'Weather Error';
        let message = error.message;

        if (error.message.includes('City not found')) {
            title = 'City Not Found';
            message = `We couldn't find "${this.lastSearchedCity}". Please check the spelling and try again.`;
        } else if (error.message.includes('Network')) {
            title = 'Connection Error';
            message = 'Please check your internet connection and try again.';
        } else if (error.message.includes('API key')) {
            title = 'Configuration Error';
            message = 'There\'s an issue with the API configuration. Please contact support.';
        }

        this.showError(title, message);
    }

    /**
     * Set loading state
     */
    setLoadingState(loading) {
        this.isLoading = loading;
        
        // Update button
        this.searchButton.disabled = loading;
        const buttonText = this.searchButton.querySelector('.button-text');
        const spinner = this.searchButton.querySelector('.loading-spinner');
        
        if (loading) {
            buttonText.style.display = 'none';
            spinner.style.display = 'inline';
            this.searchButton.setAttribute('aria-label', 'Loading weather data...');
        } else {
            buttonText.style.display = 'inline';
            spinner.style.display = 'none';
            this.searchButton.setAttribute('aria-label', 'Get weather information');
        }

        // Update input
        this.cityInput.disabled = loading;
        
        // Show/hide loading state
        this.loadingState.style.display = loading ? 'block' : 'none';
    }

    /**
     * Show weather display
     */
    showWeatherDisplay() {
        this.weatherDisplay.style.display = 'block';
        this.weatherDisplay.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    /**
     * Hide weather display
     */
    hideWeatherDisplay() {
        this.weatherDisplay.style.display = 'none';
    }

    /**
     * Show error message
     */
    showError(title, message) {
        document.getElementById('error-title').textContent = title;
        document.getElementById('error-message').textContent = message;
        this.errorDisplay.style.display = 'block';
        this.errorDisplay.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    /**
     * Hide error message
     */
    hideError() {
        this.errorDisplay.style.display = 'none';
    }

    /**
     * Cache management
     */
    getCachedData(key) {
        const cached = this.cache.get(key);
        if (cached && (Date.now() - cached.timestamp) < 300000) { // 5 minutes cache
            return cached.data;
        }
        return null;
    }

    setCachedData(key, data) {
        this.cache.set(key, {
            data: data,
            timestamp: Date.now()
        });
    }

    clearCache() {
        this.cache.clear();
        this.debugMetrics.cacheHits = 0;
        console.log('🗑️ Cache cleared');
    }

    /**
     * Debug panel methods
     */
    initializeDebugPanel() {
        this.updateDebugDisplay();
    }

    updateDebugState(state) {
        const stateElement = document.getElementById('debug-state');
        if (stateElement) {
            stateElement.textContent = state;
        }
    }

    updateDebugMetrics(responseTime, success) {
        if (success) {
            this.debugMetrics.successCount++;
            this.debugMetrics.lastSuccess = new Date();
        }
        
        this.debugMetrics.totalResponseTime += responseTime;
        this.updateDebugDisplay();
    }

    updateDebugDisplay() {
        // Update request count
        const requestCountEl = document.getElementById('debug-request-count');
        if (requestCountEl) {
            requestCountEl.textContent = this.debugMetrics.requestCount;
        }

        // Update error count
        const errorCountEl = document.getElementById('debug-error-count');
        if (errorCountEl) {
            errorCountEl.textContent = this.debugMetrics.errorCount;
        }

        // Update success rate
        const successRateEl = document.getElementById('debug-success-rate');
        if (successRateEl && this.debugMetrics.requestCount > 0) {
            const rate = Math.round((this.debugMetrics.successCount / this.debugMetrics.requestCount) * 100);
            successRateEl.textContent = `${rate}%`;
        }

        // Update average response time
        const avgTimeEl = document.getElementById('debug-avg-time');
        if (avgTimeEl && this.debugMetrics.successCount > 0) {
            const avgTime = Math.round(this.debugMetrics.totalResponseTime / this.debugMetrics.successCount);
            avgTimeEl.textContent = `${avgTime}ms`;
        }

        // Update last success
        const lastSuccessEl = document.getElementById('debug-last-success');
        if (lastSuccessEl && this.debugMetrics.lastSuccess) {
            lastSuccessEl.textContent = this.debugMetrics.lastSuccess.toLocaleString();
        }

        // Update cache hits
        const cacheHitsEl = document.getElementById('debug-cache-hits');
        if (cacheHitsEl) {
            cacheHitsEl.textContent = this.debugMetrics.cacheHits;
        }
    }

    /**
     * Debug event handlers
     */
    handleDebugToggle() {
        const content = document.getElementById('debug-content');
        const toggle = document.getElementById('debug-toggle');
        
        if (content.style.display === 'none') {
            content.style.display = 'block';
            toggle.textContent = '▼';
        } else {
            content.style.display = 'none';
            toggle.textContent = '▶';
        }
    }

    handleDebugExport() {
        const debugData = {
            metrics: this.debugMetrics,
            cache: Array.from(this.cache.entries()),
            timestamp: new Date().toISOString(),
            config: window.weatherConfig.getStatus()
        };

        const blob = new Blob([JSON.stringify(debugData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `weather-debug-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    handleCacheClear() {
        this.clearCache();
        this.updateDebugDisplay();
    }

    handleMetricsReset() {
        this.debugMetrics = {
            requestCount: 0,
            errorCount: 0,
            successCount: 0,
            totalResponseTime: 0,
            lastSuccess: null,
            cacheHits: 0
        };
        this.updateDebugDisplay();
        console.log('📊 Metrics reset');
    }
}

// Initialize the app when the page loads
const weatherApp = new WeatherApp();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => weatherApp.init());
} else {
    weatherApp.init();
}

// Make app instance available globally for debugging
window.weatherApp = weatherApp;