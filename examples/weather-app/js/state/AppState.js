/**
 * Application State Management
 * Centralized state management with observer pattern for component updates
 */

import { STORAGE_KEYS, APP_CONFIG, ERROR_MESSAGES, FEATURES } from '../constants/config.js';
import { StorageService } from '../services/StorageService.js';

/**
 * Weather data structure
 * @typedef {Object} WeatherData
 * @property {Object} location - Location information
 * @property {Object} current - Current weather data
 * @property {Array} forecast - Forecast data array
 * @property {number} lastUpdated - Timestamp of last update
 */

/**
 * User settings structure
 * @typedef {Object} UserSettings
 * @property {string} units - Temperature units ('metric' or 'imperial')
 * @property {string} theme - Theme preference ('light', 'dark', or 'auto')
 * @property {boolean} autoLocation - Auto-detect location preference
 * @property {string} language - Language preference
 * @property {boolean} showNotifications - Show weather notifications
 */

/**
 * UI state structure
 * @typedef {Object} UIState
 * @property {boolean} loading - Loading state
 * @property {string|null} error - Current error message
 * @property {string} activeView - Active view ('current', 'forecast', 'settings')
 * @property {boolean} isOnline - Online/offline status
 * @property {string|null} lastRefresh - Last refresh timestamp
 */

/**
 * Application state structure
 * @typedef {Object} AppStateData
 * @property {Object|null} currentLocation - Current selected location
 * @property {Array} favoriteLocations - Array of favorite locations
 * @property {WeatherData|null} weatherData - Current weather data
 * @property {UserSettings} settings - User preferences
 * @property {UIState} ui - UI state
 */

/**
 * State change event
 * @typedef {Object} StateChangeEvent
 * @property {string} type - Type of change
 * @property {*} payload - Change payload
 * @property {*} previousValue - Previous state value
 * @property {*} newValue - New state value
 */

/**
 * Application State Manager
 * Manages centralized application state with observer pattern
 */
export class AppState {
  constructor() {
    // Initialize storage service
    this.storage = new StorageService();

    // State observers
    this.observers = new Map();
    this.globalObservers = new Set();

    // State update queue for batching
    this.updateQueue = [];
    this.isUpdating = false;
    this.batchUpdateTimer = null;

    // Performance monitoring
    this.updateCount = 0;
    this.lastUpdateTime = 0;

    // Initialize default state
    this.state = this.getInitialState();

    // Load persisted state
    this.loadPersistedState();

    // Bind methods
    this.setState = this.setState.bind(this);
    this.getState = this.getState.bind(this);
    this.subscribe = this.subscribe.bind(this);
    this.unsubscribe = this.unsubscribe.bind(this);

    // Setup online/offline detection
    this.setupOnlineDetection();

    // Setup periodic state cleanup
    this.setupStateCleanup();

    if (FEATURES.DEBUG_MODE) {
      console.log('[AppState] Initialized with state:', this.state);
      this.enableDebugMode();
    }
  }

  /**
   * Get initial application state
   * @returns {AppStateData} - Initial state object
   */
  getInitialState() {
    return {
      currentLocation: null,
      favoriteLocations: [],
      weatherData: null,
      settings: {
        units: APP_CONFIG.DEFAULT_UNITS,
        theme: APP_CONFIG.DEFAULT_THEME,
        autoLocation: APP_CONFIG.DEFAULT_AUTO_LOCATION,
        language: APP_CONFIG.DEFAULT_LANGUAGE,
        showNotifications: false,
        refreshInterval: APP_CONFIG.DEFAULT_REFRESH_INTERVAL
      },
      ui: {
        loading: false,
        error: null,
        activeView: 'current',
        isOnline: navigator.onLine,
        lastRefresh: null,
        searchQuery: '',
        isSearching: false,
        showForecast: true,
        sidebarOpen: false
      },
      cache: {
        weatherData: new Map(),
        locations: new Map(),
        lastCleanup: Date.now()
      }
    };
  }

  /**
   * Load persisted state from storage
   */
  async loadPersistedState() {
    try {
      // Load user settings
      const settings = await this.storage.getItem(STORAGE_KEYS.USER_SETTINGS);
      if (settings) {
        this.state.settings = {
          ...this.state.settings,
          ...this.validateSettings(settings)
        };
      }

      // Load favorite locations
      const favorites = await this.storage.getItem(STORAGE_KEYS.FAVORITE_LOCATIONS);
      if (Array.isArray(favorites)) {
        this.state.favoriteLocations = favorites.filter(this.isValidLocation);
      }

      // Load current location
      const currentLocation = await this.storage.getItem(STORAGE_KEYS.CURRENT_LOCATION);
      if (currentLocation && this.isValidLocation(currentLocation)) {
        this.state.currentLocation = currentLocation;
      }

      // Load cached weather data
      const cachedWeather = await this.storage.getItem(STORAGE_KEYS.WEATHER_CACHE);
      if (cachedWeather && this.isValidWeatherData(cachedWeather)) {
        // Check if cache is still valid
        const age = Date.now() - (cachedWeather.lastUpdated || 0);
        if (age < APP_CONFIG.CACHE.WEATHER_TTL) {
          this.state.weatherData = cachedWeather;
        }
      }

      // Load UI state (limited items)
      const uiState = await this.storage.getItem(STORAGE_KEYS.UI_STATE);
      if (uiState) {
        this.state.ui = {
          ...this.state.ui,
          activeView: uiState.activeView || 'current',
          showForecast: uiState.showForecast !== undefined ? uiState.showForecast : true
        };
      }

      if (FEATURES.DEBUG_MODE) {
        console.log('[AppState] Loaded persisted state');
      }

    } catch (error) {
      console.warn('[AppState] Failed to load persisted state:', error);
    }
  }

  /**
   * Update application state
   * @param {Object|Function} updates - State updates object or function
   * @param {Object} options - Update options
   */
  setState(updates, options = {}) {
    const {
      batch = false,
      skipPersist = false,
      skipNotify = false,
      source = 'unknown'
    } = options;

    // Add to update queue if batching
    if (batch) {
      this.updateQueue.push({ updates, options: { ...options, batch: false } });
      this.scheduleBatchUpdate();
      return;
    }

    try {
      const previousState = this.deepClone(this.state);
      
      // Apply updates
      if (typeof updates === 'function') {
        this.state = updates(this.state);
      } else {
        this.state = this.mergeState(this.state, updates);
      }

      // Validate state
      this.validateState();

      // Performance tracking
      this.updateCount++;
      this.lastUpdateTime = Date.now();

      // Persist state if needed
      if (!skipPersist) {
        this.persistState();
      }

      // Notify observers if needed
      if (!skipNotify) {
        this.notifyObservers(updates, previousState, source);
      }

      if (FEATURES.DEBUG_MODE) {
        console.log(`[AppState] State updated (${source}):`, {
          updates,
          newState: this.state,
          updateCount: this.updateCount
        });
      }

    } catch (error) {
      console.error('[AppState] State update failed:', error);
      this.handleStateError(error);
    }
  }

  /**
   * Get current application state
   * @param {string} path - Optional state path to get specific value
   * @returns {*} - Current state or specific state value
   */
  getState(path = null) {
    if (!path) {
      return this.deepClone(this.state);
    }

    // Get nested state value by path
    const keys = path.split('.');
    let value = this.state;

    for (const key of keys) {
      if (value && typeof value === 'object' && key in value) {
        value = value[key];
      } else {
        return undefined;
      }
    }

    return this.deepClone(value);
  }

  /**
   * Subscribe to state changes
   * @param {string|Function} pathOrCallback - State path or global callback
   * @param {Function} callback - Callback function (if path provided)
   * @returns {Function} - Unsubscribe function
   */
  subscribe(pathOrCallback, callback = null) {
    // Global subscription
    if (typeof pathOrCallback === 'function') {
      const globalCallback = pathOrCallback;
      this.globalObservers.add(globalCallback);
      
      return () => this.globalObservers.delete(globalCallback);
    }

    // Path-specific subscription
    const path = pathOrCallback;
    if (!this.observers.has(path)) {
      this.observers.set(path, new Set());
    }
    
    this.observers.get(path).add(callback);

    // Return unsubscribe function
    return () => {
      const pathObservers = this.observers.get(path);
      if (pathObservers) {
        pathObservers.delete(callback);
        if (pathObservers.size === 0) {
          this.observers.delete(path);
        }
      }
    };
  }

  /**
   * Unsubscribe from state changes
   * @param {string} path - State path
   * @param {Function} callback - Callback function
   */
  unsubscribe(path, callback) {
    const pathObservers = this.observers.get(path);
    if (pathObservers) {
      pathObservers.delete(callback);
      if (pathObservers.size === 0) {
        this.observers.delete(path);
      }
    }
  }

  /**
   * Clear all subscriptions
   */
  clearSubscriptions() {
    this.observers.clear();
    this.globalObservers.clear();
  }

  /**
   * Merge state updates with current state
   * @param {Object} currentState - Current state
   * @param {Object} updates - State updates
   * @returns {Object} - Merged state
   */
  mergeState(currentState, updates) {
    const merged = { ...currentState };

    for (const [key, value] of Object.entries(updates)) {
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        // Deep merge objects
        merged[key] = {
          ...merged[key],
          ...value
        };
      } else {
        // Direct assignment for primitives and arrays
        merged[key] = value;
      }
    }

    return merged;
  }

  /**
   * Schedule batched state update
   */
  scheduleBatchUpdate() {
    if (this.batchUpdateTimer) {
      clearTimeout(this.batchUpdateTimer);
    }

    this.batchUpdateTimer = setTimeout(() => {
      this.processBatchUpdates();
    }, APP_CONFIG.STATE.BATCH_DELAY);
  }

  /**
   * Process queued batch updates
   */
  processBatchUpdates() {
    if (this.updateQueue.length === 0) return;

    const updates = this.updateQueue.splice(0);
    this.batchUpdateTimer = null;

    // Merge all updates
    const mergedUpdates = updates.reduce((acc, { updates: update }) => {
      return this.mergeState(acc, update);
    }, {});

    // Apply merged updates
    this.setState(mergedUpdates, {
      batch: false,
      source: 'batch'
    });
  }

  /**
   * Notify state change observers
   * @param {Object} updates - State updates
   * @param {Object} previousState - Previous state
   * @param {string} source - Update source
   */
  notifyObservers(updates, previousState, source) {
    const changeEvent = {
      type: 'stateChange',
      updates,
      previousState,
      newState: this.state,
      source,
      timestamp: Date.now()
    };

    // Notify global observers
    this.globalObservers.forEach(callback => {
      try {
        callback(changeEvent);
      } catch (error) {
        console.error('[AppState] Observer error:', error);
      }
    });

    // Notify path-specific observers
    this.observers.forEach((callbacks, path) => {
      const pathValue = this.getState(path);
      const previousPathValue = this.getStateFromObject(previousState, path);

      // Only notify if path value changed
      if (!this.deepEqual(pathValue, previousPathValue)) {
        const pathChangeEvent = {
          ...changeEvent,
          path,
          value: pathValue,
          previousValue: previousPathValue
        };

        callbacks.forEach(callback => {
          try {
            callback(pathChangeEvent);
          } catch (error) {
            console.error('[AppState] Path observer error:', error);
          }
        });
      }
    });
  }

  /**
   * Persist state to storage
   */
  async persistState() {
    try {
      // Persist user settings
      await this.storage.setItem(STORAGE_KEYS.USER_SETTINGS, this.state.settings);

      // Persist favorite locations
      await this.storage.setItem(STORAGE_KEYS.FAVORITE_LOCATIONS, this.state.favoriteLocations);

      // Persist current location
      if (this.state.currentLocation) {
        await this.storage.setItem(STORAGE_KEYS.CURRENT_LOCATION, this.state.currentLocation);
      }

      // Persist weather data (with timestamp)
      if (this.state.weatherData) {
        const weatherToCache = {
          ...this.state.weatherData,
          lastUpdated: Date.now()
        };
        await this.storage.setItem(STORAGE_KEYS.WEATHER_CACHE, weatherToCache);
      }

      // Persist limited UI state
      const uiToPersist = {
        activeView: this.state.ui.activeView,
        showForecast: this.state.ui.showForecast
      };
      await this.storage.setItem(STORAGE_KEYS.UI_STATE, uiToPersist);

    } catch (error) {
      console.warn('[AppState] Failed to persist state:', error);
    }
  }

  /**
   * Validate application state
   */
  validateState() {
    // Validate settings
    if (this.state.settings) {
      this.state.settings = this.validateSettings(this.state.settings);
    }

    // Validate locations
    if (this.state.currentLocation && !this.isValidLocation(this.state.currentLocation)) {
      this.state.currentLocation = null;
    }

    if (this.state.favoriteLocations) {
      this.state.favoriteLocations = this.state.favoriteLocations.filter(this.isValidLocation);
    }

    // Validate UI state
    if (this.state.ui) {
      const validViews = ['current', 'forecast', 'settings'];
      if (!validViews.includes(this.state.ui.activeView)) {
        this.state.ui.activeView = 'current';
      }
    }
  }

  /**
   * Validate user settings
   * @param {Object} settings - Settings to validate
   * @returns {Object} - Validated settings
   */
  validateSettings(settings) {
    const validUnits = ['metric', 'imperial'];
    const validThemes = ['light', 'dark', 'auto'];
    const validLanguages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja'];

    return {
      units: validUnits.includes(settings.units) ? settings.units : APP_CONFIG.DEFAULT_UNITS,
      theme: validThemes.includes(settings.theme) ? settings.theme : APP_CONFIG.DEFAULT_THEME,
      autoLocation: typeof settings.autoLocation === 'boolean' ? settings.autoLocation : APP_CONFIG.DEFAULT_AUTO_LOCATION,
      language: validLanguages.includes(settings.language) ? settings.language : APP_CONFIG.DEFAULT_LANGUAGE,
      showNotifications: typeof settings.showNotifications === 'boolean' ? settings.showNotifications : false,
      refreshInterval: typeof settings.refreshInterval === 'number' && settings.refreshInterval >= 300000 
        ? settings.refreshInterval 
        : APP_CONFIG.DEFAULT_REFRESH_INTERVAL
    };
  }

  /**
   * Validate location object
   * @param {Object} location - Location to validate
   * @returns {boolean} - Whether location is valid
   */
  isValidLocation(location) {
    return location &&
           typeof location === 'object' &&
           typeof location.name === 'string' &&
           typeof location.lat === 'number' &&
           typeof location.lon === 'number' &&
           location.lat >= -90 &&
           location.lat <= 90 &&
           location.lon >= -180 &&
           location.lon <= 180;
  }

  /**
   * Validate weather data
   * @param {Object} weatherData - Weather data to validate
   * @returns {boolean} - Whether weather data is valid
   */
  isValidWeatherData(weatherData) {
    return weatherData &&
           typeof weatherData === 'object' &&
           weatherData.location &&
           weatherData.current &&
           typeof weatherData.lastUpdated === 'number';
  }

  /**
   * Setup online/offline detection
   */
  setupOnlineDetection() {
    const updateOnlineStatus = () => {
      this.setState({
        ui: {
          isOnline: navigator.onLine
        }
      }, { source: 'onlineStatus' });
    };

    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);

    // Store cleanup function
    this._cleanupOnlineDetection = () => {
      window.removeEventListener('online', updateOnlineStatus);
      window.removeEventListener('offline', updateOnlineStatus);
    };
  }

  /**
   * Setup periodic state cleanup
   */
  setupStateCleanup() {
    this.cleanupInterval = setInterval(() => {
      this.cleanupState();
    }, APP_CONFIG.STATE.CLEANUP_INTERVAL);
  }

  /**
   * Cleanup expired state data
   */
  cleanupState() {
    const now = Date.now();
    let cleaned = false;

    // Clean expired weather cache
    if (this.state.weatherData) {
      const age = now - (this.state.weatherData.lastUpdated || 0);
      if (age > APP_CONFIG.CACHE.WEATHER_TTL) {
        this.setState({
          weatherData: null
        }, { source: 'cleanup' });
        cleaned = true;
      }
    }

    // Clean expired location cache
    if (this.state.cache && this.state.cache.locations) {
      const locationCache = new Map();
      this.state.cache.locations.forEach((data, key) => {
        const age = now - (data.timestamp || 0);
        if (age < APP_CONFIG.CACHE.LOCATION_TTL) {
          locationCache.set(key, data);
        } else {
          cleaned = true;
        }
      });

      if (cleaned) {
        this.setState({
          cache: {
            ...this.state.cache,
            locations: locationCache,
            lastCleanup: now
          }
        }, { source: 'cleanup' });
      }
    }

    if (cleaned && FEATURES.DEBUG_MODE) {
      console.log('[AppState] State cleanup completed');
    }
  }

  /**
   * Handle state errors
   * @param {Error} error - State error
   */
  handleStateError(error) {
    // Set error state
    this.setState({
      ui: {
        error: error.message || ERROR_MESSAGES.STATE.GENERIC,
        loading: false
      }
    }, { source: 'error' });

    // Reset to safe state if corruption detected
    if (error.message && error.message.includes('corrupt')) {
      this.resetState();
    }
  }

  /**
   * Reset state to initial values
   */
  resetState() {
    this.state = this.getInitialState();
    this.storage.clear();
    
    // Notify observers of reset
    this.notifyObservers({}, {}, 'reset');

    if (FEATURES.DEBUG_MODE) {
      console.log('[AppState] State reset to initial values');
    }
  }

  /**
   * Get state value from object by path
   * @param {Object} obj - Object to search
   * @param {string} path - Path to value
   * @returns {*} - Value at path
   */
  getStateFromObject(obj, path) {
    const keys = path.split('.');
    let value = obj;

    for (const key of keys) {
      if (value && typeof value === 'object' && key in value) {
        value = value[key];
      } else {
        return undefined;
      }
    }

    return value;
  }

  /**
   * Deep clone object
   * @param {*} obj - Object to clone
   * @returns {*} - Cloned object
   */
  deepClone(obj) {
    if (obj === null || typeof obj !== 'object') {
      return obj;
    }

    if (obj instanceof Date) {
      return new Date(obj.getTime());
    }

    if (obj instanceof Map) {
      return new Map(obj);
    }

    if (obj instanceof Set) {
      return new Set(obj);
    }

    if (Array.isArray(obj)) {
      return obj.map(item => this.deepClone(item));
    }

    const cloned = {};
    for (const [key, value] of Object.entries(obj)) {
      cloned[key] = this.deepClone(value);
    }

    return cloned;
  }

  /**
   * Deep equality check
   * @param {*} a - First value
   * @param {*} b - Second value
   * @returns {boolean} - Whether values are deeply equal
   */
  deepEqual(a, b) {
    if (a === b) return true;
    
    if (a instanceof Date && b instanceof Date) {
      return a.getTime() === b.getTime();
    }

    if (!a || !b || typeof a !== 'object' || typeof b !== 'object') {
      return a === b;
    }

    const keysA = Object.keys(a);
    const keysB = Object.keys(b);

    if (keysA.length !== keysB.length) return false;

    for (const key of keysA) {
      if (!keysB.includes(key)) return false;
      if (!this.deepEqual(a[key], b[key])) return false;
    }

    return true;
  }

  /**
   * Enable debug mode with additional logging
   */
  enableDebugMode() {
    // Add state change logging
    this.subscribe((changeEvent) => {
      console.group(`[AppState] State Change - ${changeEvent.source}`);
      console.log('Updates:', changeEvent.updates);
      console.log('Previous State:', changeEvent.previousState);
      console.log('New State:', changeEvent.newState);
      console.log('Timestamp:', new Date(changeEvent.timestamp).toISOString());
      console.groupEnd();
    });

    // Add performance monitoring
    const originalSetState = this.setState;
    this.setState = (updates, options = {}) => {
      const start = performance.now();
      originalSetState.call(this, updates, options);
      const end = performance.now();
      
      if (end - start > 10) { // Log slow updates
        console.warn(`[AppState] Slow state update (${(end - start).toFixed(2)}ms):`, updates);
      }
    };

    // Expose state to global for debugging
    window._appState = this;
  }

  /**
   * Get state statistics
   * @returns {Object} - State statistics
   */
  getStateStats() {
    return {
      updateCount: this.updateCount,
      lastUpdateTime: this.lastUpdateTime,
      observerCount: Array.from(this.observers.values()).reduce((sum, set) => sum + set.size, 0),
      globalObserverCount: this.globalObservers.size,
      queuedUpdates: this.updateQueue.length,
      cacheSize: this.state.cache ? this.state.cache.locations.size : 0,
      stateSize: JSON.stringify(this.state).length
    };
  }

  /**
   * Cleanup resources
   */
  destroy() {
    // Clear timers
    if (this.batchUpdateTimer) {
      clearTimeout(this.batchUpdateTimer);
    }
    
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }

    // Cleanup online detection
    if (this._cleanupOnlineDetection) {
      this._cleanupOnlineDetection();
    }

    // Clear observers
    this.clearSubscriptions();

    // Clear update queue
    this.updateQueue = [];

    if (FEATURES.DEBUG_MODE) {
      console.log('[AppState] Destroyed');
    }
  }
}

// Create singleton instance
export const appState = new AppState();

// Export convenience methods
export const setState = appState.setState.bind(appState);
export const getState = appState.getState.bind(appState);
export const subscribe = appState.subscribe.bind(appState);
export const unsubscribe = appState.unsubscribe.bind(appState);

export default appState;