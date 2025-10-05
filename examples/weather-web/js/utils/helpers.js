/**
 * Utility helper functions for Weather Dashboard
 * Contains common functions for data transformation, formatting, and utilities
 */

/**
 * Convert temperature from Kelvin to Celsius
 * @param {number} kelvin - Temperature in Kelvin
 * @returns {number} Temperature in Celsius (rounded to nearest integer)
 */
export function kelvinToCelsius(kelvin) {
    if (typeof kelvin !== 'number' || isNaN(kelvin)) {
        throw new Error('Invalid temperature value');
    }
    return Math.round(kelvin - 273.15);
}

/**
 * Convert temperature from Kelvin to Fahrenheit
 * @param {number} kelvin - Temperature in Kelvin
 * @returns {number} Temperature in Fahrenheit (rounded to nearest integer)
 */
export function kelvinToFahrenheit(kelvin) {
    if (typeof kelvin !== 'number' || isNaN(kelvin)) {
        throw new Error('Invalid temperature value');
    }
    return Math.round((kelvin - 273.15) * 9/5 + 32);
}

/**
 * Format temperature with unit symbol
 * @param {number} temperature - Temperature value
 * @param {string} unit - Temperature unit ('C' for Celsius, 'F' for Fahrenheit)
 * @returns {string} Formatted temperature string (e.g., "20°C")
 */
export function formatTemperature(temperature, unit = 'C') {
    if (typeof temperature !== 'number' || isNaN(temperature)) {
        return '--°';
    }
    
    const rounded = Math.round(temperature);
    return `${rounded}°${unit.toUpperCase()}`;
}

/**
 * Convert wind degree to cardinal direction
 * @param {number} degrees - Wind direction in degrees (0-360)
 * @returns {string} Cardinal direction (N, NE, E, SE, S, SW, W, NW)
 */
export function getWindDirection(degrees) {
    if (typeof degrees !== 'number' || isNaN(degrees)) {
        return 'N/A';
    }
    
    const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const index = Math.round(degrees / 45) % 8;
    return directions[index];
}

/**
 * Capitalize first letter of each word in a string
 * @param {string} text - Text to capitalize
 * @returns {string} Capitalized text
 */
export function capitalizeWords(text) {
    if (typeof text !== 'string') {
        return '';
    }
    
    return text
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
}

/**
 * Format date for display
 * @param {Date|number} date - Date object or timestamp
 * @param {Object} options - Formatting options
 * @returns {string} Formatted date string
 */
export function formatDate(date, options = {}) {
    try {
        const dateObj = date instanceof Date ? date : new Date(date * 1000);
        
        const defaultOptions = {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            ...options
        };
        
        return dateObj.toLocaleDateString(navigator.language, defaultOptions);
    } catch (error) {
        console.error('Date formatting error:', error);
        return 'Invalid Date';
    }
}

/**
 * Format time for display
 * @param {Date|number} date - Date object or timestamp
 * @param {Object} options - Formatting options
 * @returns {string} Formatted time string
 */
export function formatTime(date, options = {}) {
    try {
        const dateObj = date instanceof Date ? date : new Date(date * 1000);
        
        const defaultOptions = {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
            ...options
        };
        
        return dateObj.toLocaleTimeString(navigator.language, defaultOptions);
    } catch (error) {
        console.error('Time formatting error:', error);
        return 'Invalid Time';
    }
}

/**
 * Debounce function - delays execution until after delay period
 * @param {Function} func - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(func, delay) {
    let timeoutId;
    
    return function debounced(...args) {
        clearTimeout(timeoutId);
        
        timeoutId = setTimeout(() => {
            func.apply(this, args);
        }, delay);
    };
}

/**
 * Throttle function - limits execution to once per interval
 * @param {Function} func - Function to throttle
 * @param {number} interval - Minimum interval between calls in milliseconds
 * @returns {Function} Throttled function
 */
export function throttle(func, interval) {
    let lastCall = 0;
    
    return function throttled(...args) {
        const now = Date.now();
        
        if (now - lastCall >= interval) {
            lastCall = now;
            func.apply(this, args);
        }
    };
}

/**
 * Deep clone an object
 * @param {any} obj - Object to clone
 * @returns {any} Deep copy of the object
 */
export function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') {
        return obj;
    }
    
    if (obj instanceof Date) {
        return new Date(obj.getTime());
    }
    
    if (obj instanceof Array) {
        return obj.map(item => deepClone(item));
    }
    
    if (typeof obj === 'object') {
        const cloned = {};
        for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
                cloned[key] = deepClone(obj[key]);
            }
        }
        return cloned;
    }
    
    return obj;
}

/**
 * Generate unique identifier
 * @returns {string} Unique ID string
 */
export function generateId() {
    return Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
}

/**
 * Check if value is empty (null, undefined, empty string, empty array, empty object)
 * @param {any} value - Value to check
 * @returns {boolean} True if empty
 */
export function isEmpty(value) {
    if (value == null) return true;
    if (typeof value === 'string' || Array.isArray(value)) return value.length === 0;
    if (typeof value === 'object') return Object.keys(value).length === 0;
    return false;
}

/**
 * Sanitize HTML string to prevent XSS
 * @param {string} html - HTML string to sanitize
 * @returns {string} Sanitized HTML string
 */
export function sanitizeHtml(html) {
    if (typeof html !== 'string') {
        return '';
    }
    
    const div = document.createElement('div');
    div.textContent = html;
    return div.innerHTML;
}

/**
 * Get color based on temperature range
 * @param {number} temp - Temperature in Celsius
 * @returns {string} CSS custom property name for temperature color
 */
export function getTemperatureColor(temp) {
    if (temp < 0) return '--temp-cold';
    if (temp < 15) return '--temp-mild';
    if (temp < 25) return '--temp-warm';
    return '--temp-hot';
}

/**
 * Convert wind speed from m/s to other units
 * @param {number} meterPerSecond - Wind speed in m/s
 * @param {string} unit - Target unit ('kmh', 'mph', 'knots')
 * @returns {number} Converted wind speed
 */
export function convertWindSpeed(meterPerSecond, unit = 'kmh') {
    if (typeof meterPerSecond !== 'number' || isNaN(meterPerSecond)) {
        return 0;
    }
    
    switch (unit.toLowerCase()) {
        case 'kmh':
        case 'km/h':
            return Math.round(meterPerSecond * 3.6);
        case 'mph':
            return Math.round(meterPerSecond * 2.237);
        case 'knots':
            return Math.round(meterPerSecond * 1.944);
        default:
            return Math.round(meterPerSecond);
    }
}

/**
 * Validate coordinates
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @returns {boolean} True if coordinates are valid
 */
export function isValidCoordinates(lat, lon) {
    return typeof lat === 'number' && 
           typeof lon === 'number' && 
           lat >= -90 && lat <= 90 && 
           lon >= -180 && lon <= 180;
}

/**
 * Calculate distance between two coordinates using Haversine formula
 * @param {number} lat1 - First latitude
 * @param {number} lon1 - First longitude  
 * @param {number} lat2 - Second latitude
 * @param {number} lon2 - Second longitude
 * @returns {number} Distance in kilometers
 */
export function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in kilometers
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    
    const a = 
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
        Math.sin(dLon/2) * Math.sin(dLon/2);
    
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    const distance = R * c;
    
    return Math.round(distance * 10) / 10; // Round to 1 decimal place
}