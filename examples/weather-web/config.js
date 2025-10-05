/**
 * Configuration management for Weather App
 * Handles API key loading and validation
 */

class WeatherConfig {
    constructor() {
        this.apiKey = null;
        this.baseUrl = 'https://api.openweathermap.org/data/2.5';
        this.units = 'metric';
        this.initialized = false;
    }

    /**
     * Initialize configuration by loading API key
     * In production, API key should be loaded from server endpoint
     * For development, it can be set directly here
     */
    async init() {
        try {
            // In a real production environment, this would fetch from a secure endpoint
            // For now, developers need to replace 'your_api_key_here' with actual key
            this.apiKey = await this.loadApiKey();
            
            if (!this.apiKey || this.apiKey === 'your_api_key_here') {
                throw new Error('OpenWeatherMap API key not configured');
            }

            this.validateApiKey();
            this.initialized = true;
            
            console.log('Weather configuration initialized successfully');
            return true;
        } catch (error) {
            console.error('Failed to initialize weather configuration:', error.message);
            this.showConfigurationError(error.message);
            return false;
        }
    }

    /**
     * Load API key from environment or configuration
     * In production, this should make a secure server request
     */
    async loadApiKey() {
        // Method 1: Try to load from a secure endpoint (recommended for production)
        try {
            const response = await fetch('/api/config');
            if (response.ok) {
                const config = await response.json();
                return config.apiKey;
            }
        } catch (error) {
            console.warn('Could not load API key from server endpoint');
        }

        // Method 2: Load from environment variable (Node.js environment)
        if (typeof process !== 'undefined' && process.env) {
            return process.env.OPENWEATHER_API_KEY;
        }

        // Method 3: For development - replace with your actual API key
        // NEVER commit real API keys to version control!
        return 'your_api_key_here';
    }

    /**
     * Validate API key format
     * OpenWeatherMap API keys are 32-character hexadecimal strings
     */
    validateApiKey() {
        if (!this.apiKey) {
            throw new Error('API key is required');
        }

        // Basic format validation - OpenWeatherMap keys are typically 32 chars
        if (typeof this.apiKey !== 'string' || this.apiKey.length < 20) {
            throw new Error('Invalid API key format');
        }

        // Check for placeholder values
        const placeholders = ['your_api_key_here', 'INSERT_KEY_HERE', 'API_KEY'];
        if (placeholders.includes(this.apiKey)) {
            throw new Error('Please replace placeholder with actual OpenWeatherMap API key');
        }
    }

    /**
     * Test API key by making a simple request
     */
    async testApiConnection() {
        if (!this.initialized) {
            throw new Error('Configuration not initialized');
        }

        try {
            const testUrl = `${this.baseUrl}/weather?q=London&appid=${this.apiKey}&units=${this.units}`;
            const response = await fetch(testUrl);
            
            if (!response.ok) {
                if (response.status === 401) {
                    throw new Error('Invalid API key - check your OpenWeatherMap credentials');
                } else if (response.status === 429) {
                    throw new Error('API rate limit exceeded - please try again later');
                } else {
                    throw new Error(`API test failed with status: ${response.status}`);
                }
            }

            const data = await response.json();
            console.log('API connection test successful:', data.name);
            return true;
        } catch (error) {
            console.error('API connection test failed:', error.message);
            throw error;
        }
    }

    /**
     * Get complete API URL for weather requests
     */
    getWeatherUrl(city) {
        if (!this.initialized) {
            throw new Error('Configuration not initialized - call init() first');
        }

        if (!city || typeof city !== 'string') {
            throw new Error('City name is required');
        }

        const encodedCity = encodeURIComponent(city.trim());
        return `${this.baseUrl}/weather?q=${encodedCity}&appid=${this.apiKey}&units=${this.units}`;
    }

    /**
     * Show configuration error to user
     */
    showConfigurationError(message) {
        // Create or update error display
        let errorElement = document.getElementById('config-error');
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.id = 'config-error';
            errorElement.className = 'error-message config-error';
            
            // Insert at the top of the page
            const container = document.querySelector('.container') || document.body;
            container.insertBefore(errorElement, container.firstChild);
        }

        errorElement.innerHTML = `
            <h3>⚠️ Configuration Error</h3>
            <p>${message}</p>
            <div class="setup-instructions">
                <h4>Setup Instructions:</h4>
                <ol>
                    <li>Sign up for a free account at <a href="https://openweathermap.org/api" target="_blank">OpenWeatherMap</a></li>
                    <li>Get your API key from your account dashboard</li>
                    <li>Replace "your_api_key_here" in config.js with your actual API key</li>
                    <li>Refresh the page to try again</li>
                </ol>
            </div>
        `;

        errorElement.style.display = 'block';
    }

    /**
     * Hide configuration error message
     */
    hideConfigurationError() {
        const errorElement = document.getElementById('config-error');
        if (errorElement) {
            errorElement.style.display = 'none';
        }
    }

    /**
     * Get configuration status for debug panel
     */
    getStatus() {
        return {
            initialized: this.initialized,
            hasApiKey: !!this.apiKey,
            baseUrl: this.baseUrl,
            units: this.units
        };
    }
}

// Create global configuration instance
window.weatherConfig = new WeatherConfig();

// CSS for configuration error display
const configStyles = `
    .config-error {
        background: #ffe6e6;
        border: 2px solid #ff4444;
        border-radius: 8px;
        padding: 20px;
        margin: 20px 0;
        color: #d32f2f;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .config-error h3 {
        margin: 0 0 10px 0;
        color: #d32f2f;
    }

    .config-error h4 {
        margin: 15px 0 10px 0;
        color: #d32f2f;
    }

    .config-error ol {
        margin: 10px 0;
        padding-left: 20px;
    }

    .config-error li {
        margin: 5px 0;
        line-height: 1.4;
    }

    .config-error a {
        color: #1976d2;
        text-decoration: underline;
    }

    .config-error a:hover {
        text-decoration: none;
    }

    .setup-instructions {
        background: #fff;
        padding: 15px;
        border-radius: 4px;
        border-left: 4px solid #ff4444;
        margin-top: 15px;
    }
`;

// Inject CSS styles
const styleSheet = document.createElement('style');
styleSheet.textContent = configStyles;
document.head.appendChild(styleSheet);