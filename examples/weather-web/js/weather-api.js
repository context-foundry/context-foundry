/**
 * Weather API service for fetching weather data
 * Handles API calls with proper error handling and caching
 */
class WeatherAPI {
    constructor() {
        this.apiKey = 'YOUR_API_KEY'; // Replace with actual API key
        this.baseUrl = 'https://api.openweathermap.org/data/2.5';
        this.geoUrl = 'https://api.openweathermap.org/geo/1.0';
        this.cache = new Map();
        this.cacheDuration = 10 * 60 * 1000; // 10 minutes
    }

    /**
     * Get current weather by city name
     * @param {string} cityName - City name to search
     * @returns {Promise<Object>} Weather data
     */
    async getCurrentWeather(cityName) {
        const cacheKey = `current-${cityName.toLowerCase()}`;
        const cached = this.getFromCache(cacheKey);
        
        if (cached) {
            return cached;
        }

        try {
            const response = await fetch(
                `${this.baseUrl}/weather?q=${encodeURIComponent(cityName)}&appid=${this.apiKey}&units=metric`
            );

            if (!response.ok) {
                throw new Error(this.getErrorMessage(response.status));
            }

            const data = await response.json();
            this.setCache(cacheKey, data);
            return data;
        } catch (error) {
            console.error('Weather API error:', error);
            throw error;
        }
    }

    /**
     * Get current weather by coordinates
     * @param {number} lat - Latitude
     * @param {number} lon - Longitude
     * @returns {Promise<Object>} Weather data
     */
    async getCurrentWeatherByCoords(lat, lon) {
        const cacheKey = `current-${lat}-${lon}`;
        const cached = this.getFromCache(cacheKey);
        
        if (cached) {
            return cached;
        }

        try {
            const response = await fetch(
                `${this.baseUrl}/weather?lat=${lat}&lon=${lon}&appid=${this.apiKey}&units=metric`
            );

            if (!response.ok) {
                throw new Error(this.getErrorMessage(response.status));
            }

            const data = await response.json();
            this.setCache(cacheKey, data);
            return data;
        } catch (error) {
            console.error('Weather API error:', error);
            throw error;
        }
    }

    /**
     * Get 5-day forecast by city name
     * @param {string} cityName - City name to search
     * @returns {Promise<Object>} Forecast data
     */
    async getForecast(cityName) {
        const cacheKey = `forecast-${cityName.toLowerCase()}`;
        const cached = this.getFromCache(cacheKey);
        
        if (cached) {
            return cached;
        }

        try {
            const response = await fetch(
                `${this.baseUrl}/forecast?q=${encodeURIComponent(cityName)}&appid=${this.apiKey}&units=metric`
            );

            if (!response.ok) {
                throw new Error(this.getErrorMessage(response.status));
            }

            const data = await response.json();
            this.setCache(cacheKey, data);
            return data;
        } catch (error) {
            console.error('Forecast API error:', error);
            throw error;
        }
    }

    /**
     * Get 5-day forecast by coordinates
     * @param {number} lat - Latitude
     * @param {number} lon - Longitude
     * @returns {Promise<Object>} Forecast data
     */
    async getForecastByCoords(lat, lon) {
        const cacheKey = `forecast-${lat}-${lon}`;
        const cached = this.getFromCache(cacheKey);
        
        if (cached) {
            return cached;
        }

        try {
            const response = await fetch(
                `${this.baseUrl}/forecast?lat=${lat}&lon=${lon}&appid=${this.apiKey}&units=metric`
            );

            if (!response.ok) {
                throw new Error(this.getErrorMessage(response.status));
            }

            const data = await response.json();
            this.setCache(cacheKey, data);
            return data;
        } catch (error) {
            console.error('Forecast API error:', error);
            throw error;
        }
    }

    /**
     * Search cities by name for suggestions
     * @param {string} query - Search query
     * @returns {Promise<Array>} City suggestions
     */
    async searchCities(query) {
        if (query.length < 2) {
            return [];
        }

        try {
            const response = await fetch(
                `${this.geoUrl}/direct?q=${encodeURIComponent(query)}&limit=5&appid=${this.apiKey}`
            );

            if (!response.ok) {
                return [];
            }

            const data = await response.json();
            return data.map(city => ({
                name: city.name,
                country: city.country,
                state: city.state,
                lat: city.lat,
                lon: city.lon,
                displayName: `${city.name}, ${city.state ? city.state + ', ' : ''}${city.country}`
            }));
        } catch (error) {
            console.error('City search error:', error);
            return [];
        }
    }

    /**
     * Get weather icon URL
     * @param {string} iconCode - Icon code from API
     * @returns {string} Icon URL
     */
    getIconUrl(iconCode) {
        return `https://openweathermap.org/img/wn/${iconCode}@2x.png`;
    }

    /**
     * Get cached data if still valid
     * @param {string} key - Cache key
     * @returns {Object|null} Cached data or null
     */
    getFromCache(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cacheDuration) {
            return cached.data;
        }
        return null;
    }

    /**
     * Set data in cache
     * @param {string} key - Cache key
     * @param {Object} data - Data to cache
     */
    setCache(key, data) {
        this.cache.set(key, {
            data,
            timestamp: Date.now()
        });
    }

    /**
     * Get user-friendly error message
     * @param {number} status - HTTP status code
     * @returns {string} Error message
     */
    getErrorMessage(status) {
        switch (status) {
            case 401:
                return 'Invalid API key. Please check your configuration.';
            case 404:
                return 'Location not found. Please try a different city name.';
            case 429:
                return 'Too many requests. Please try again later.';
            case 500:
            case 502:
            case 503:
                return 'Weather service temporarily unavailable. Please try again later.';
            default:
                return 'Unable to fetch weather data. Please check your internet connection.';
        }
    }
}

// Initialize weather API
window.weatherAPI = new WeatherAPI();