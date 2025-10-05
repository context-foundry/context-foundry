/**
 * Weather display manager
 * Handles rendering weather data and forecast information
 */
class WeatherDisplay {
    constructor() {
        this.currentWeatherElement = document.getElementById('weather-display');
        this.forecastContainer = document.getElementById('forecast-container');
        
        this.init();
    }

    /**
     * Initialize display manager
     */
    init() {
        // Set up any event listeners or initial state
        this.setupEventListeners();
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Add keyboard navigation for forecast items
        document.addEventListener('click', (e) => {
            if (e.target.closest('.forecast-item')) {
                const item = e.target.closest('.forecast-item');
                this.showForecastDetails(item);
            }
        });
    }

    /**
     * Display current weather data
     * @param {Object} weatherData - Weather data from API
     */
    displayCurrentWeather(weatherData) {
        try {
            // Update location and date
            document.getElementById('current-location').textContent = 
                `${weatherData.name}, ${weatherData.sys.country}`;
            document.getElementById('current-date').textContent = 
                this.formatDate(new Date());

            // Update weather icon and temperature
            const iconElement = document.getElementById('weather-icon');
            iconElement.src = window.weatherAPI.getIconUrl(weatherData.weather[0].icon);
            iconElement.alt = `Weather icon: ${weatherData.weather[0].description}`;

            document.getElementById('current-temp').textContent = 
                `${Math.round(weatherData.main.temp)}°C`;
            document.getElementById('current-temp').setAttribute('aria-label', 
                `Current temperature ${Math.round(weatherData.main.temp)} degrees Celsius`);

            // Update weather details
            document.getElementById('weather-condition').textContent = 
                this.capitalize(weatherData.weather[0].description);
            document.getElementById('feels-like').textContent = 
                `${Math.round(weatherData.main.feels_like)}°C`;
            document.getElementById('humidity').textContent = 
                `${weatherData.main.humidity}%`;
            document.getElementById('wind-speed').textContent = 
                `${weatherData.wind.speed} m/s`;

            // Show weather display
            this.currentWeatherElement.hidden = false;
            this.currentWeatherElement.scrollIntoView({ behavior: 'smooth', block: 'start' });

            // Announce to screen readers
            window.accessibilityManager?.announce(
                `Weather updated for ${weatherData.name}. Current temperature ${Math.round(weatherData.main.temp)} degrees Celsius. ${weatherData.weather[0].description}`
            );

        } catch (error) {
            console.error('Error displaying weather data:', error);
            this.showError('Error displaying weather data');
        }
    }

    /**
     * Display forecast data
     * @param {Object} forecastData - Forecast data from API
     */
    displayForecast(forecastData) {
        try {
            // Clear existing forecast
            this.forecastContainer.innerHTML = '';

            // Group forecast by day (API returns 3-hour intervals)
            const dailyForecasts = this.groupForecastByDay(forecastData.list);

            dailyForecasts.forEach((dayForecast, index) => {
                const forecastItem = this.createForecastItem(dayForecast, index);
                this.forecastContainer.appendChild(forecastItem);
            });

            // Setup keyboard navigation
            this.setupForecastNavigation();

        } catch (error) {
            console.error('Error displaying forecast data:', error);
            this.showError('Error displaying forecast data');
        }
    }

    /**
     * Create forecast item element
     * @param {Object} dayForecast - Day forecast data
     * @param {number} index - Day index
     * @returns {HTMLElement} Forecast item element
     */
    createForecastItem(dayForecast, index) {
        const item = document.createElement('div');
        item.className = 'forecast-item';
        item.tabIndex = index === 0 ? 0 : -1;
        item.setAttribute('role', 'button');
        item.setAttribute('aria-label', 
            `Forecast for ${this.formatForecastDay(dayForecast.date)}. High ${Math.round(dayForecast.high)} degrees, low ${Math.round(dayForecast.low)} degrees. ${dayForecast.description}`
        );

        const dayName = this.formatForecastDay(dayForecast.date);
        const iconUrl = window.weatherAPI.getIconUrl(dayForecast.icon);

        item.innerHTML = `
            <div class="forecast-day">${dayName}</div>
            <img src="${iconUrl}" 
                 alt="${dayForecast.description}" 
                 class="forecast-icon">
            <div class="forecast-temps">
                <span class="forecast-high">${Math.round(dayForecast.high)}°</span>
                <span class="forecast-low">${Math.round(dayForecast.low)}°</span>
            </div>
            <div class="forecast-description visually-hidden">${dayForecast.description}</div>
        `;

        return item;
    }

    /**
     * Group forecast data by day
     * @param {Array} forecastList - List of forecast items
     * @returns {Array} Grouped forecast by day
     */
    groupForecastByDay(forecastList) {
        const dailyData = {};
        const today = new Date().toDateString();

        forecastList.forEach(item => {
            const date = new Date(item.dt * 1000);
            const dateKey = date.toDateString();
            
            // Skip today's data as we show current weather
            if (dateKey === today) return;

            if (!dailyData[dateKey]) {
                dailyData[dateKey] = {
                    date: date,
                    temps: [],
                    descriptions: [],
                    icons: []
                };
            }

            dailyData[dateKey].temps.push(item.main.temp);
            dailyData[dateKey].descriptions.push(item.weather[0].description);
            dailyData[dateKey].icons.push(item.weather[0].icon);
        });

        // Convert to array and calculate daily highs/lows
        return Object.values(dailyData)
            .slice(0, 5) // Only show 5 days
            .map(day => ({
                date: day.date,
                high: Math.max(...day.temps),
                low: Math.min(...day.temps),
                description: this.getMostCommonDescription(day.descriptions),
                icon: this.getMostCommonIcon(day.icons)
            }));
    }

    /**
     * Get most common description from array
     * @param {Array} descriptions - Array of weather descriptions
     * @returns {string} Most common description
     */
    getMostCommonDescription(descriptions) {
        const counts = {};
        descriptions.forEach(desc => {
            counts[desc] = (counts[desc] || 0) + 1;
        });
        return Object.keys(counts).reduce((a, b) => counts[a] > counts[b] ? a : b);
    }

    /**
     * Get most common icon from array
     * @param {Array} icons - Array of weather icons
     * @returns {string} Most common icon
     */
    getMostCommonIcon(icons) {
        const counts = {};
        icons.forEach(icon => {
            counts[icon] = (counts[icon] || 0) + 1;
        });
        return Object.keys(counts).reduce((a, b) => counts[a] > counts[b] ? a : b);
    }

    /**
     * Setup keyboard navigation for forecast items
     */
    setupForecastNavigation() {
        const items = this.forecastContainer.querySelectorAll('.forecast-item');
        items.forEach((item, index) => {
            item.addEventListener('keydown', (e) => {
                this.handleForecastKeydown(e, items, index);
            });
        });
    }

    /**
     * Handle keydown events for forecast items
     * @param {KeyboardEvent} e - Keyboard event
     * @param {NodeList} items - Forecast items
     * @param {number} currentIndex - Current item index
     */
    handleForecastKeydown(e, items, currentIndex) {
        let targetIndex = currentIndex;

        switch (e.key) {
            case 'ArrowRight':
                e.preventDefault();
                targetIndex = (currentIndex + 1) % items.length;
                break;
            case 'ArrowLeft':
                e.preventDefault();
                targetIndex = currentIndex === 0 ? items.length - 1 : currentIndex - 1;
                break;
            case 'Home':
                e.preventDefault();
                targetIndex = 0;
                break;
            case 'End':
                e.preventDefault();
                targetIndex = items.length - 1;
                break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                this.showForecastDetails(items[currentIndex]);
                break;
        }

        if (targetIndex !== currentIndex) {
            // Update tabindex
            items[currentIndex].tabIndex = -1;
            items[targetIndex].tabIndex = 0;
            items[targetIndex].focus();
        }
    }

    /**
     * Show detailed forecast information
     * @param {HTMLElement} item - Forecast item element
     */
    showForecastDetails(item) {
        const description = item.querySelector('.forecast-description').textContent;
        const day = item.querySelector('.forecast-day').textContent;
        
        window.accessibilityManager?.announce(`Detailed forecast for ${day}: ${description}`);
    }

    /**
     * Format date for display
     * @param {Date} date - Date to format
     * @returns {string} Formatted date string
     */
    formatDate(date) {
        return date.toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }

    /**
     * Format forecast day
     * @param {Date} date - Date to format
     * @returns {string} Formatted day string
     */
    formatForecastDay(date) {
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);

        if (date.toDateString() === tomorrow.toDateString()) {
            return 'Tomorrow';
        }

        return date.toLocaleDateString('en-US', { weekday: 'short' });
    }

    /**
     * Capitalize first letter of string
     * @param {string} str - String to capitalize
     * @returns {string} Capitalized string
     */
    capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    /**
     * Show error message
     * @param {string} message - Error message
     */
    showError(message) {
        const errorElement = document.getElementById('error-message');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.hidden = false;
            
            // Hide after 5 seconds
            setTimeout(() => {
                errorElement.hidden = true;
            }, 5000);
        }
    }

    /**
     * Hide weather display
     */
    hide() {
        this.currentWeatherElement.hidden = true;
    }
}

// Initialize weather display
window.weatherDisplay = new WeatherDisplay();