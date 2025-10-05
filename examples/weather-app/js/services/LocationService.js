/**
 * Location Service
 * Handles geolocation detection, location search, and geocoding
 */

import { WEATHER_API, APP_CONFIG, ERROR_MESSAGES, STORAGE_KEYS, FEATURES } from '../constants/config.js';
import { getCached, buildURL, APIError } from '../utils/api.js';

/**
 * Location data interface
 * @typedef {Object} Location
 * @property {string} name - Location name
 * @property {string} country - Country code
 * @property {string} state - State/region (optional)
 * @property {number} lat - Latitude
 * @property {number} lon - Longitude
 */

/**
 * Geolocation coordinates
 * @typedef {Object} Coordinates
 * @property {number} latitude - Latitude
 * @property {number} longitude - Longitude
 * @property {number} accuracy - Accuracy in meters
 */

/**
 * Location Service class
 * Provides geolocation and location search functionality
 */
export class LocationService {
  constructor() {
    this.currentPosition = null;
    this.watchId = null;
    this.isWatching = false;
    this.lastKnownLocation = this.loadLastKnownLocation();
    
    // Bind methods to maintain context
    this.getCurrentLocation = this.getCurrentLocation.bind(this);
    this.searchLocations = this.searchLocations.bind(this);
    this.reverseGeocode = this.reverseGeocode.bind(this);
  }

  /**
   * Check if geolocation is supported
   * @returns {boolean} - Whether geolocation is available
   */
  isGeolocationSupported() {
    return FEATURES.ENABLE_GEOLOCATION && 'geolocation' in navigator;
  }

  /**
   * Get current user location using browser geolocation API
   * @param {Object} options - Geolocation options
   * @returns {Promise<Coordinates>} - Current coordinates
   * @throws {APIError} - If geolocation fails or is denied
   */
  async getCurrentLocation(options = {}) {
    if (!this.isGeolocationSupported()) {
      throw new APIError(ERROR_MESSAGES.GEOLOCATION.UNAVAILABLE, 0);
    }

    const geolocationOptions = {
      enableHighAccuracy: APP_CONFIG.GEOLOCATION.ENABLE_HIGH_ACCURACY,
      timeout: APP_CONFIG.GEOLOCATION.TIMEOUT,
      maximumAge: APP_CONFIG.GEOLOCATION.MAXIMUM_AGE,
      ...options
    };

    return new Promise((resolve, reject) => {
      const successCallback = (position) => {
        const coordinates = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: new Date(position.timestamp)
        };

        this.currentPosition = coordinates;
        this.saveLastKnownLocation(coordinates);

        if (FEATURES.DEBUG_MODE) {
          console.log('[Location] Current position obtained:', coordinates);
        }

        resolve(coordinates);
      };

      const errorCallback = (error) => {
        let errorMessage;
        
        switch (error.code) {
          case error.PERMISSION_DENIED:
            errorMessage = ERROR_MESSAGES.GEOLOCATION.DENIED;
            break;
          case error.POSITION_UNAVAILABLE:
            errorMessage = ERROR_MESSAGES.GEOLOCATION.UNAVAILABLE;
            break;
          case error.TIMEOUT:
            errorMessage = ERROR_MESSAGES.GEOLOCATION.TIMEOUT;
            break;
          default:
            errorMessage = ERROR_MESSAGES.GEOLOCATION.GENERIC;
        }

        if (FEATURES.DEBUG_MODE) {
          console.error('[Location] Geolocation error:', error);
        }

        reject(new APIError(errorMessage, error.code));
      };

      navigator.geolocation.getCurrentPosition(
        successCallback,
        errorCallback,
        geolocationOptions
      );
    });
  }

  /**
   * Start watching user's location for changes
   * @param {Function} callback - Callback for position updates
   * @param {Object} options - Geolocation options
   * @returns {number} - Watch ID for stopping watch
   */
  watchLocation(callback, options = {}) {
    if (!this.isGeolocationSupported()) {
      throw new APIError(ERROR_MESSAGES.GEOLOCATION.UNAVAILABLE, 0);
    }

    if (this.isWatching) {
      this.stopWatchingLocation();
    }

    const geolocationOptions = {
      enableHighAccuracy: APP_CONFIG.GEOLOCATION.ENABLE_HIGH_ACCURACY,
      timeout: APP_CONFIG.GEOLOCATION.TIMEOUT,
      maximumAge: APP_CONFIG.GEOLOCATION.MAXIMUM_AGE,
      ...options
    };

    const successCallback = (position) => {
      const coordinates = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
        timestamp: new Date(position.timestamp)
      };

      this.currentPosition = coordinates;
      this.saveLastKnownLocation(coordinates);
      callback(coordinates);
    };

    const errorCallback = (error) => {
      if (FEATURES.DEBUG_MODE) {
        console.error('[Location] Watch location error:', error);
      }
      
      callback(null, new APIError(ERROR_MESSAGES.GEOLOCATION.GENERIC, error.code));
    };

    this.watchId = navigator.geolocation.watchPosition(
      successCallback,
      errorCallback,
      geolocationOptions
    );

    this.isWatching = true;

    if (FEATURES.DEBUG_MODE) {
      console.log('[Location] Started watching location, watch ID:', this.watchId);
    }

    return this.watchId;
  }

  /**
   * Stop watching user's location
   */
  stopWatchingLocation() {
    if (this.watchId !== null && this.isGeolocationSupported()) {
      navigator.geolocation.clearWatch(this.watchId);
      this.watchId = null;
      this.isWatching = false;

      if (FEATURES.DEBUG_MODE) {
        console.log('[Location] Stopped watching location');
      }
    }
  }

  /**
   * Search for locations by name using OpenWeatherMap Geocoding API
   * @param {string} query - Search query (city name)
   * @param {number} limit - Maximum number of results
   * @returns {Promise<Location[]>} - Array of matching locations
   */
  async searchLocations(query, limit = APP_CONFIG.SEARCH.MAX_RESULTS) {
    if (!query || query.trim().length < APP_CONFIG.SEARCH.MIN_QUERY_LENGTH) {
      throw new APIError(ERROR_MESSAGES.SEARCH.MIN_LENGTH, 0);
    }

    const trimmedQuery = query.trim();
    const url = buildURL(`${WEATHER_API.GEO_URL}${WEATHER_API.ENDPOINTS.DIRECT_GEOCODING}`, {
      q: trimmedQuery,
      limit: Math.min(limit, APP_CONFIG.SEARCH.RESULT_LIMIT),
      appid: WEATHER_API.API_KEY
    });

    try {
      const results = await getCached(url, {}, {
        cacheTTL: APP_CONFIG.CACHE.GEOCODING_TTL
      });

      if (!Array.isArray(results)) {
        throw new APIError(ERROR_MESSAGES.DATA.INVALID_RESPONSE);
      }

      if (results.length === 0) {
        throw new APIError(ERROR_MESSAGES.SEARCH.NO_RESULTS, 404);
      }

      // Transform API response to our Location format
      const locations = results.map(item => ({
        name: item.name || 'Unknown',
        country: item.country || '',
        state: item.state || '',
        lat: item.lat || 0,
        lon: item.lon || 0,
        localNames: item.local_names || {}
      }));

      if (FEATURES.DEBUG_MODE) {
        console.log(`[Location] Search results for "${trimmedQuery}":`, locations);
      }

      return locations;

    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }
      throw new APIError(ERROR_MESSAGES.NETWORK.GENERIC, 0);
    }
  }

  /**
   * Get location name from coordinates (reverse geocoding)
   * @param {number} lat - Latitude
   * @param {number} lon - Longitude
   * @param {number} limit - Maximum number of results
   * @returns {Promise<Location[]>} - Array of locations at coordinates
   */
  async reverseGeocode(lat, lon, limit = 1) {
    if (typeof lat !== 'number' || typeof lon !== 'number') {
      throw new APIError('Invalid coordinates provided', 0);
    }

    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      throw new APIError('Coordinates out of valid range', 0);
    }

    const url = buildURL(`${WEATHER_API.GEO_URL}${WEATHER_API.ENDPOINTS.REVERSE_GEOCODING}`, {
      lat: lat.toFixed(6),
      lon: lon.toFixed(6),
      limit: Math.min(limit, 5),
      appid: WEATHER_API.API_KEY
    });

    try {
      const results = await getCached(url, {}, {
        cacheTTL: APP_CONFIG.CACHE.GEOCODING_TTL
      });

      if (!Array.isArray(results) || results.length === 0) {
        throw new APIError('No location found for coordinates', 404);
      }

      // Transform API response to our Location format
      const locations = results.map(item => ({
        name: item.name || 'Unknown',
        country: item.country || '',
        state: item.state || '',
        lat: item.lat || lat,
        lon: item.lon || lon,
        localNames: item.local_names || {}
      }));

      if (FEATURES.DEBUG_MODE) {
        console.log(`[Location] Reverse geocoding for ${lat}, ${lon}:`, locations);
      }

      return locations;

    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }
      throw new APIError(ERROR_MESSAGES.NETWORK.GENERIC, 0);
    }
  }

  /**
   * Get location details from coordinates
   * @param {number} lat - Latitude
   * @param {number} lon - Longitude
   * @returns {Promise<Location>} - Location details
   */
  async getLocationFromCoordinates(lat, lon) {
    const locations = await this.reverseGeocode(lat, lon, 1);
    return locations[0] || {
      name: `${lat.toFixed(2)}, ${lon.toFixed(2)}`,
      country: '',
      state: '',
      lat,
      lon
    };
  }

  /**
   * Get user's current location with address details
   * @returns {Promise<Location>} - Current location with details
   */
  async getCurrentLocationWithDetails() {
    try {
      const coordinates = await this.getCurrentLocation();
      return await this.getLocationFromCoordinates(
        coordinates.latitude,
        coordinates.longitude
      );
    } catch (error) {
      // Fallback to last known location if available
      if (this.lastKnownLocation) {
        return await this.getLocationFromCoordinates(
          this.lastKnownLocation.latitude,
          this.lastKnownLocation.longitude
        );
      }
      throw error;
    }
  }

  /**
   * Calculate distance between two coordinates using Haversine formula
   * @param {number} lat1 - First latitude
   * @param {number} lon1 - First longitude
   * @param {number} lat2 - Second latitude
   * @param {number} lon2 - Second longitude
   * @returns {number} - Distance in kilometers
   */
  calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in kilometers
    const dLat = this.toRadians(lat2 - lat1);
    const dLon = this.toRadians(lon2 - lon1);
    
    const a = 
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(this.toRadians(lat1)) * Math.cos(this.toRadians(lat2)) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
    
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  /**
   * Convert degrees to radians
   * @param {number} degrees - Degrees to convert
   * @returns {number} - Radians
   */
  toRadians(degrees) {
    return degrees * (Math.PI / 180);
  }

  /**
   * Format location for display
   * @param {Location} location - Location object
   * @returns {string} - Formatted location string
   */
  formatLocation(location) {
    if (!location) return 'Unknown Location';

    const parts = [location.name];
    
    if (location.state && location.state !== location.name) {
      parts.push(location.state);
    }
    
    if (location.country) {
      parts.push(location.country);
    }

    return parts.join(', ');
  }

  /**
   * Check if location is valid
   * @param {Location} location - Location to validate
   * @returns {boolean} - Whether location is valid
   */
  isValidLocation(location) {
    return location &&
           typeof location.lat === 'number' &&
           typeof location.lon === 'number' &&
           location.lat >= -90 &&
           location.lat <= 90 &&
           location.lon >= -180 &&
           location.lon <= 180;
  }

  /**
   * Save last known location to local storage
   * @param {Coordinates} coordinates - Coordinates to save
   */
  saveLastKnownLocation(coordinates) {
    if (!FEATURES.ENABLE_LOCAL_STORAGE) return;

    try {
      const locationData = {
        latitude: coordinates.latitude,
        longitude: coordinates.longitude,
        accuracy: coordinates.accuracy,
        timestamp: coordinates.timestamp || new Date()
      };

      localStorage.setItem(STORAGE_KEYS.LAST_LOCATION, JSON.stringify(locationData));
      this.lastKnownLocation = locationData;

      if (FEATURES.DEBUG_MODE) {
        console.log('[Location] Saved last known location:', locationData);
      }
    } catch (error) {
      if (FEATURES.DEBUG_MODE) {
        console.warn('[Location] Failed to save last known location:', error);
      }
    }
  }

  /**
   * Load last known location from local storage
   * @returns {Coordinates|null} - Last known coordinates or null
   */
  loadLastKnownLocation() {
    if (!FEATURES.ENABLE_LOCAL_STORAGE) return null;

    try {
      const stored = localStorage.getItem(STORAGE_KEYS.LAST_LOCATION);
      if (!stored) return null;

      const locationData = JSON.parse(stored);
      
      // Check if location is recent (within 24 hours)
      const age = Date.now() - new Date(locationData.timestamp).getTime();
      const maxAge = 24 * 60 * 60 * 1000; // 24 hours
      
      if (age > maxAge) {
        localStorage.removeItem(STORAGE_KEYS.LAST_LOCATION);
        return null;
      }

      if (FEATURES.DEBUG_MODE) {
        console.log('[Location] Loaded last known location:', locationData);
      }

      return locationData;
    } catch (error) {
      if (FEATURES.DEBUG_MODE) {
        console.warn('[Location] Failed to load last known location:', error);
      }
      return null;
    }
  }

  /**
   * Clear saved location data
   */
  clearLocationData() {
    if (!FEATURES.ENABLE_LOCAL_STORAGE) return;

    try {
      localStorage.removeItem(STORAGE_KEYS.LAST_LOCATION);
      this.lastKnownLocation = null;
      this.currentPosition = null;

      if (FEATURES.DEBUG_MODE) {
        console.log('[Location] Cleared location data');
      }
    } catch (error) {
      if (FEATURES.DEBUG_MODE) {
        console.warn('[Location] Failed to clear location data:', error);
      }
    }
  }

  /**
   * Get popular/default locations
   * @returns {Location[]} - Array of popular locations
   */
  getPopularLocations() {
    return APP_CONFIG.DEFAULT_LOCATIONS.map(location => ({
      ...location,
      isDefault: true
    }));
  }

  /**
   * Clean up resources
   */
  destroy() {
    this.stopWatchingLocation();
    this.currentPosition = null;
    this.lastKnownLocation = null;
  }
}

// Create singleton instance
export const locationService = new LocationService();

// Export individual functions for convenience
export const getCurrentLocation = locationService.getCurrentLocation;
export const searchLocations = locationService.searchLocations;
export const reverseGeocode = locationService.reverseGeocode;
export const getLocationFromCoordinates = locationService.getLocationFromCoordinates;
export const getCurrentLocationWithDetails = locationService.getCurrentLocationWithDetails;
export const calculateDistance = locationService.calculateDistance;
export const formatLocation = locationService.formatLocation;
export const isValidLocation = locationService.isValidLocation;

export default locationService;