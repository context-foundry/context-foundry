/**
 * Weather Web Application
 * Current Implementation: Uses PAID OpenWeatherMap API endpoint
 * Issue: Application hangs at "Loading weather data..." due to paid endpoint requirements
 */

class WeatherApp {
    constructor() {
        // CURRENT CONFIGURATION - PAID ENDPOINT (CAUSING THE ISSUE)
        this.API_CONFIG = {
            // This is the PAID/Pro endpoint that requires subscription
            BASE_URL: 'https://pro.openweathermap.org/data/2.5/weather',
            API_KEY: 'your_paid_api_key_here', // Requires paid subscription
            UNITS: 'metric'
        };
        
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
        
        this.initializeEventListeners();
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

        try {
            this.showLoading();
            this.disableSearch();
            
            const weatherData = await this.fetchWeatherData(city);
            this.displayWeatherData(weatherData);
            
        } catch (error) {
            console.error('Weather fetch error:', error);
            this.showError(this.getErrorMessage(error));
        } finally {
            this.enableSearch();
        }
    }

    /**
     * Fetch weather data from API
     * CURRENT ISSUE: Uses paid endpoint that requires subscription
     * This causes the request to fail/hang without proper credentials
     */
    async fetchWeatherData(city) {
        const url = `${this.API_CONFIG.BASE_URL}?q=${encodeURIComponent(city)}&appid=${this.API_CONFIG.API_KEY}&units=${this.API_CONFIG.UNITS}`;
        
        console.log('Fetching weather data from PAID endpoint:', url);
        
        // PROBLEM: No timeout handling - requests hang indefinitely
        const response = await fetch(url);
        
        // PROBLEM: Inadequate error handling for paid endpoint failures
        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('PAID_API_AUTH_FAILED');
            } else if (response.status === 403) {
                throw new Error('PAID_API_FORBIDDEN');
            } else if (response.status === 404) {
                throw new Error('CITY_NOT_FOUND');
            } else {
                throw new Error('API_ERROR');
            }
        }

        return await response.json();
    }

    /**
     * Display weather data in the UI
     */
    displayWeatherData(data) {
        this.hideLoading();
        this.hideError();
        
        // Populate weather information
        this.cityName.textContent = `${data.name}, ${data.sys.country}`;
        this.temp.textContent = Math.round(data.main.temp);
        this.description.textContent = data.weather[0].description;
        this.feelsLike.textContent = Math.round(data.main.feels_like);
        this.humidity.textContent = data.main.humidity;
        this.windSpeed.textContent = data.wind.speed.toFixed(1);
        
        this.weatherResult.classList.remove('hidden');
    }

    /**
     * Show loading state
     * CURRENT ISSUE: This message gets stuck when paid endpoint fails
     */
    showLoading() {
        this.loadingMessage.classList.remove('hidden');
        this.hideError();
        this.hideWeatherResult();
    }

    /**
     * Hide loading state
     * PROBLEM: This may never get called if request hangs
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
    }

    /**
     * Enable search functionality
     */
    enableSearch() {
        this.searchBtn.disabled = false;
        this.cityInput.disabled = false;
    }

    /**
     * Get user-friendly error message
     * CURRENT ISSUE: Doesn't handle paid endpoint specific errors well
     */
    getErrorMessage(error) {
        switch (error.message) {
            case 'PAID_API_AUTH_FAILED':
                return 'API authentication failed - paid subscription required';
            case 'PAID_API_FORBIDDEN':
                return 'Access forbidden - paid API key required';
            case 'CITY_NOT_FOUND':
                return 'City not found. Please check the spelling and try again.';
            case 'API_ERROR':
                return 'Weather service is currently unavailable. Please try again later.';
            case 'Failed to fetch':
                return 'Network error. Please check your internet connection.';
            default:
                return 'An unexpected error occurred. Please try again.';
        }
    }
}

// ANALYSIS SUMMARY - CURRENT ISSUES IDENTIFIED:
// 1. Uses paid OpenWeatherMap Pro endpoint (pro.openweathermap.org)
// 2. Requires paid API key for authentication
// 3. No timeout handling - requests hang indefinitely
// 4. Inadequate error handling for paid endpoint failures
// 5. Loading message gets stuck when API calls fail
// 6. No retry mechanism for failed requests

// Initialize the weather application
document.addEventListener('DOMContentLoaded', () => {
    window.weatherApp = new WeatherApp();
    console.log('Weather App initialized with PAID endpoint configuration');
    console.log('Current API endpoint:', window.weatherApp.API_CONFIG.BASE_URL);
    console.log('Known issue: Application hangs at "Loading weather data..." due to paid endpoint');
});