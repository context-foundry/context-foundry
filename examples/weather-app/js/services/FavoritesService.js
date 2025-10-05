/**
 * Favorites Service
 * Manages user's favorite locations with persistence, synchronization, and validation
 */

import { STORAGE_KEYS, APP_CONFIG, ERROR_MESSAGES, FEATURES } from '../constants/config.js';
import { StorageService } from './StorageService.js';
import { LocationService } from './LocationService.js';
import { AppError, ERROR_TYPES } from '../utils/error-handler.js';

/**
 * Favorite location structure
 * @typedef {Object} FavoriteLocation
 * @property {string} id - Unique identifier
 * @property {string} name - Location display name
 * @property {string} country - Country name/code
 * @property {string} state - State/region (optional)
 * @property {number} lat - Latitude
 * @property {number} lon - Longitude
 * @property {number} addedAt - Timestamp when added
 * @property {number} lastViewed - Last viewed timestamp
 * @property {number} viewCount - Number of times viewed
 * @property {boolean} isPinned - Whether location is pinned
 * @property {Object} metadata - Additional metadata
 * @property {string} timezone - Timezone identifier
 * @property {string} localNames - Local names in different languages
 */

/**
 * Favorites change event
 * @typedef {Object} FavoritesChangeEvent
 * @property {string} type - Change type ('add', 'remove', 'update', 'reorder')
 * @property {FavoriteLocation|FavoriteLocation[]} data - Changed data
 * @property {number} count - Total favorites count
 * @property {string} source - Event source
 */

/**
 * Favorites Service Class
 * Manages favorite locations with CRUD operations and persistence
 */
export class FavoritesService {
  constructor(options = {}) {
    this.options = {
      maxFavorites: APP_CONFIG.FAVORITES?.MAX_COUNT || 20,
      enableSync: true,
      enableValidation: true,
      enableMetrics: true,
      storageKey: STORAGE_KEYS.FAVORITE_LOCATIONS,
      ...options
    };

    // Storage service for persistence
    this.storage = new StorageService();
    this.locationService = new LocationService();

    // In-memory favorites cache
    this.favorites = new Map();
    this.favoritesList = [];

    // Event listeners for changes
    this.listeners = new Set();

    // Service metrics
    this.metrics = {
      totalAdded: 0,
      totalRemoved: 0,
      totalViews: 0,
      lastActivity: 0
    };

    // Initialization state
    this.initialized = false;
    this.initializing = false;

    // Bind methods
    this.add = this.add.bind(this);
    this.remove = this.remove.bind(this);
    this.get = this.get.bind(this);
    this.getAll = this.getAll.bind(this);
    this.updateViewCount = this.updateViewCount.bind(this);

    if (FEATURES.DEBUG_MODE) {
      console.log('[FavoritesService] Initialized with options:', this.options);
    }
  }

  /**
   * Initialize favorites service
   * @returns {Promise<void>}
   */
  async initialize() {
    if (this.initialized || this.initializing) {
      return;
    }

    this.initializing = true;

    try {
      // Load favorites from storage
      await this.loadFavorites();

      // Load metrics
      await this.loadMetrics();

      // Setup storage sync if enabled
      if (this.options.enableSync) {
        this.setupStorageSync();
      }

      this.initialized = true;
      this.initializing = false;

      if (FEATURES.DEBUG_MODE) {
        console.log('[FavoritesService] Initialized with', this.favorites.size, 'favorites');
      }

    } catch (error) {
      this.initializing = false;
      console.error('[FavoritesService] Initialization failed:', error);
      throw new AppError('Failed to initialize favorites service', ERROR_TYPES.STORAGE, {
        source: 'FavoritesService.initialize',
        context: { error }
      });
    }
  }

  /**
   * Load favorites from storage
   * @returns {Promise<void>}
   */
  async loadFavorites() {
    try {
      const stored = await this.storage.getItem(this.options.storageKey);
      
      if (Array.isArray(stored)) {
        // Validate and process stored favorites
        const validFavorites = stored
          .filter(item => this.validateFavoriteLocation(item))
          .map(item => this.normalizeFavoriteLocation(item));

        // Rebuild favorites map and list
        this.favorites.clear();
        this.favoritesList = [];

        validFavorites.forEach(favorite => {
          this.favorites.set(favorite.id, favorite);
          this.favoritesList.push(favorite);
        });

        // Sort by priority (pinned first, then by last viewed)
        this.sortFavorites();

        if (FEATURES.DEBUG_MODE) {
          console.log('[FavoritesService] Loaded', validFavorites.length, 'favorites from storage');
        }
      }

    } catch (error) {
      console.warn('[FavoritesService] Failed to load favorites from storage:', error);
      // Initialize with empty state
      this.favorites.clear();
      this.favoritesList = [];
    }
  }

  /**
   * Load metrics from storage
   * @returns {Promise<void>}
   */
  async loadMetrics() {
    try {
      const stored = await this.storage.getItem(STORAGE_KEYS.FAVORITES_METRICS);
      if (stored && typeof stored === 'object') {
        this.metrics = {
          ...this.metrics,
          ...stored
        };
      }
    } catch (error) {
      console.warn('[FavoritesService] Failed to load metrics:', error);
    }
  }

  /**
   * Save favorites to storage
   * @returns {Promise<void>}
   */
  async saveFavorites() {
    try {
      await this.storage.setItem(this.options.storageKey, this.favoritesList);
      
      if (this.options.enableMetrics) {
        this.metrics.lastActivity = Date.now();
        await this.storage.setItem(STORAGE_KEYS.FAVORITES_METRICS, this.metrics);
      }

    } catch (error) {
      console.error('[FavoritesService] Failed to save favorites:', error);
      throw new AppError('Failed to save favorites', ERROR_TYPES.STORAGE, {
        source: 'FavoritesService.saveFavorites',
        context: { error, favoritesCount: this.favoritesList.length }
      });
    }
  }

  /**
   * Add location to favorites
   * @param {Object} location - Location to add
   * @param {Object} options - Add options
   * @returns {Promise<FavoriteLocation>} - Added favorite location
   */
  async add(location, options = {}) {
    await this.ensureInitialized();

    try {
      // Validate location
      if (!this.validateLocationForFavorite(location)) {
        throw new AppError('Invalid location data', ERROR_TYPES.VALIDATION, {
          source: 'FavoritesService.add',
          context: { location }
        });
      }

      // Check if already exists
      const existing = this.findByCoordinates(location.lat, location.lon);
      if (existing) {
        throw new AppError('Location is already in favorites', ERROR_TYPES.VALIDATION, {
          source: 'FavoritesService.add',
          userMessage: 'This location is already in your favorites',
          context: { existing, location }
        });
      }

      // Check favorites limit
      if (this.favoritesList.length >= this.options.maxFavorites) {
        throw new AppError(`Maximum ${this.options.maxFavorites} favorites allowed`, ERROR_TYPES.VALIDATION, {
          source: 'FavoritesService.add',
          userMessage: `You can only have up to ${this.options.maxFavorites} favorite locations`,
          context: { currentCount: this.favoritesList.length, maxCount: this.options.maxFavorites }
        });
      }

      // Create favorite location object
      const favorite = this.createFavoriteLocation(location, options);

      // Add to cache
      this.favorites.set(favorite.id, favorite);
      this.favoritesList.push(favorite);

      // Sort favorites
      this.sortFavorites();

      // Save to storage
      await this.saveFavorites();

      // Update metrics
      this.metrics.totalAdded++;

      // Notify listeners
      this.notifyListeners({
        type: 'add',
        data: favorite,
        count: this.favoritesList.length,
        source: 'FavoritesService.add'
      });

      if (FEATURES.DEBUG_MODE) {
        console.log('[FavoritesService] Added favorite:', favorite);
      }

      return favorite;

    } catch (error) {
      if (error instanceof AppError) {
        throw error;
      }
      throw new AppError('Failed to add favorite location', ERROR_TYPES.UNKNOWN, {
        source: 'FavoritesService.add',
        context: { location, error }
      });
    }
  }

  /**
   * Remove location from favorites
   * @param {string} id - Favorite location ID
   * @returns {Promise<boolean>} - Whether location was removed
   */
  async remove(id) {
    await this.ensureInitialized();

    try {
      const favorite = this.favorites.get(id);
      if (!favorite) {
        return false;
      }

      // Remove from cache
      this.favorites.delete(id);
      this.favoritesList = this.favoritesList.filter(item => item.id !== id);

      // Save to storage
      await this.saveFavorites();

      // Update metrics
      this.metrics.totalRemoved++;

      // Notify listeners
      this.notifyListeners({
        type: 'remove',
        data: favorite,
        count: this.favoritesList.length,
        source: 'FavoritesService.remove'
      });

      if (FEATURES.DEBUG_MODE) {
        console.log('[FavoritesService] Removed favorite:', id);
      }

      return true;

    } catch (error) {
      console.error('[FavoritesService] Failed to remove favorite:', error);
      throw new AppError('Failed to remove favorite location', ERROR_TYPES.STORAGE, {
        source: 'FavoritesService.remove',
        context: { id, error }
      });
    }
  }

  /**
   * Get favorite location by ID
   * @param {string} id - Favorite location ID
   * @returns {FavoriteLocation|null} - Favorite location or null
   */
  get(id) {
    return this.favorites.get(id) || null;
  }

  /**
   * Get all favorite locations
   * @returns {FavoriteLocation[]} - Array of favorite locations
   */
  getAll() {
    return [...this.favoritesList];
  }

  /**
   * Update favorite location
   * @param {string} id - Favorite location ID
   * @param {Object} updates - Updates to apply
   * @returns {Promise<FavoriteLocation|null>} - Updated favorite location
   */
  async update(id, updates) {
    await this.ensureInitialized();

    try {
      const favorite = this.favorites.get(id);
      if (!favorite) {
        return null;
      }

      // Apply updates
      const updatedFavorite = {
        ...favorite,
        ...updates,
        id, // Preserve ID
        addedAt: favorite.addedAt, // Preserve original add time
        lastUpdated: Date.now()
      };

      // Validate updated favorite
      if (!this.validateFavoriteLocation(updatedFavorite)) {
        throw new AppError('Invalid favorite location data', ERROR_TYPES.VALIDATION);
      }

      // Update in cache
      this.favorites.set(id, updatedFavorite);
      const listIndex = this.favoritesList.findIndex(item => item.id === id);
      if (listIndex !== -1) {
        this.favoritesList[listIndex] = updatedFavorite;
      }

      // Sort if priority changed
      if ('isPinned' in updates) {
        this.sortFavorites();
      }

      // Save to storage
      await this.saveFavorites();

      // Notify listeners
      this.notifyListeners({
        type: 'update',
        data: updatedFavorite,
        count: this.favoritesList.length,
        source: 'FavoritesService.update'
      });

      return updatedFavorite;

    } catch (error) {
      if (error instanceof AppError) {
        throw error;
      }
      throw new AppError('Failed to update favorite location', ERROR_TYPES.UNKNOWN, {
        source: 'FavoritesService.update',
        context: { id, updates, error }
      });
    }
  }

  /**
   * Update view count for favorite location
   * @param {string} id - Favorite location ID
   * @returns {Promise<void>}
   */
  async updateViewCount(id) {
    const favorite = this.favorites.get(id);
    if (!favorite) return;

    const updates = {
      viewCount: (favorite.viewCount || 0) + 1,
      lastViewed: Date.now()
    };

    await this.update(id, updates);
    this.metrics.totalViews++;
  }

  /**
   * Toggle pin status of favorite location
   * @param {string} id - Favorite location ID
   * @returns {Promise<boolean>} - New pin status
   */
  async togglePin(id) {
    const favorite = this.favorites.get(id);
    if (!favorite) return false;

    const newPinStatus = !favorite.isPinned;
    await this.update(id, { isPinned: newPinStatus });
    
    return newPinStatus;
  }

  /**
   * Reorder favorites list
   * @param {string[]} orderedIds - Array of favorite IDs in new order
   * @returns {Promise<void>}
   */
  async reorder(orderedIds) {
    await this.ensureInitialized();

    try {
      // Validate that all IDs exist
      const validIds = orderedIds.filter(id => this.favorites.has(id));
      
      if (validIds.length !== this.favoritesList.length) {
        throw new AppError('Invalid reorder operation', ERROR_TYPES.VALIDATION);
      }

      // Create new ordered list
      this.favoritesList = validIds.map(id => this.favorites.get(id));

      // Save to storage
      await this.saveFavorites();

      // Notify listeners
      this.notifyListeners({
        type: 'reorder',
        data: this.favoritesList,
        count: this.favoritesList.length,
        source: 'FavoritesService.reorder'
      });

    } catch (error) {
      throw new AppError('Failed to reorder favorites', ERROR_TYPES.UNKNOWN, {
        source: 'FavoritesService.reorder',
        context: { orderedIds, error }
      });
    }
  }

  /**
   * Check if location is in favorites
   * @param {number} lat - Latitude
   * @param {number} lon - Longitude
   * @returns {boolean} - Whether location is favorited
   */
  isFavorite(lat, lon) {
    return this.findByCoordinates(lat, lon) !== null;
  }

  /**
   * Find favorite by coordinates
   * @param {number} lat - Latitude
   * @param {number} lon - Longitude
   * @returns {FavoriteLocation|null} - Favorite location or null
   */
  findByCoordinates(lat, lon) {
    const threshold = 0.001; // ~100m tolerance
    
    for (const favorite of this.favorites.values()) {
      const latDiff = Math.abs(favorite.lat - lat);
      const lonDiff = Math.abs(favorite.lon - lon);
      
      if (latDiff <= threshold && lonDiff <= threshold) {
        return favorite;
      }
    }
    
    return null;
  }

  /**
   * Search favorites by name
   * @param {string} query - Search query
   * @returns {FavoriteLocation[]} - Matching favorites
   */
  search(query) {
    if (!query || typeof query !== 'string') {
      return this.getAll();
    }

    const searchTerm = query.toLowerCase().trim();
    
    return this.favoritesList.filter(favorite => {
      return favorite.name.toLowerCase().includes(searchTerm) ||
             favorite.country.toLowerCase().includes(searchTerm) ||
             (favorite.state && favorite.state.toLowerCase().includes(searchTerm));
    });
  }

  /**
   * Get favorites sorted by different criteria
   * @param {string} sortBy - Sort criteria ('name', 'added', 'viewed', 'country')
   * @param {string} order - Sort order ('asc', 'desc')
   * @returns {FavoriteLocation[]} - Sorted favorites
   */
  getSorted(sortBy = 'added', order = 'desc') {
    const favorites = [...this.favoritesList];
    
    const sortFunctions = {
      name: (a, b) => a.name.localeCompare(b.name),
      added: (a, b) => a.addedAt - b.addedAt,
      viewed: (a, b) => (a.lastViewed || 0) - (b.lastViewed || 0),
      country: (a, b) => a.country.localeCompare(b.country),
      viewCount: (a, b) => (a.viewCount || 0) - (b.viewCount || 0)
    };

    const sortFn = sortFunctions[sortBy] || sortFunctions.added;
    
    favorites.sort((a, b) => {
      // Always sort pinned items first
      if (a.isPinned !== b.isPinned) {
        return a.isPinned ? -1 : 1;
      }
      
      const result = sortFn(a, b);
      return order === 'desc' ? -result : result;
    });

    return favorites;
  }

  /**
   * Create favorite location object
   * @param {Object} location - Source location data
   * @param {Object} options - Creation options
   * @returns {FavoriteLocation} - Created favorite location
   */
  createFavoriteLocation(location, options = {}) {
    const now = Date.now();
    const id = this.generateFavoriteId(location);

    return {
      id,
      name: location.name || 'Unknown Location',
      country: location.country || '',
      state: location.state || '',
      lat: location.lat,
      lon: location.lon,
      addedAt: now,
      lastViewed: now,
      viewCount: 0,
      isPinned: options.isPinned || false,
      metadata: {
        source: options.source || 'manual',
        timezone: location.timezone || null,
        localNames: location.localNames || {},
        ...options.metadata
      }
    };
  }

  /**
   * Generate unique ID for favorite location
   * @param {Object} location - Location data
   * @returns {string} - Generated ID
   */
  generateFavoriteId(location) {
    const latStr = location.lat.toFixed(6);
    const lonStr = location.lon.toFixed(6);
    const nameSlug = location.name.toLowerCase().replace(/[^a-z0-9]/g, '-');
    return `fav_${nameSlug}_${latStr}_${lonStr}`;
  }

  /**
   * Validate location data for adding to favorites
   * @param {Object} location - Location to validate
   * @returns {boolean} - Whether location is valid
   */
  validateLocationForFavorite(location) {
    return location &&
           typeof location.name === 'string' && location.name.trim().length > 0 &&
           typeof location.lat === 'number' &&
           typeof location.lon === 'number' &&
           location.lat >= -90 && location.lat <= 90 &&
           location.lon >= -180 && location.lon <= 180;
  }

  /**
   * Validate favorite location object
   * @param {Object} favorite - Favorite location to validate
   * @returns {boolean} - Whether favorite is valid
   */
  validateFavoriteLocation(favorite) {
    return favorite &&
           typeof favorite.id === 'string' &&
           typeof favorite.name === 'string' &&
           typeof favorite.lat === 'number' &&
           typeof favorite.lon === 'number' &&
           typeof favorite.addedAt === 'number' &&
           favorite.lat >= -90 && favorite.lat <= 90 &&
           favorite.lon >= -180 && favorite.lon <= 180;
  }

  /**
   * Normalize favorite location data
   * @param {Object} favorite - Raw favorite data
   * @returns {FavoriteLocation} - Normalized favorite
   */
  normalizeFavoriteLocation(favorite) {
    return {
      id: favorite.id,
      name: favorite.name || 'Unknown Location',
      country: favorite.country || '',
      state: favorite.state || '',
      lat: favorite.lat,
      lon: favorite.lon,
      addedAt: favorite.addedAt,
      lastViewed: favorite.lastViewed || favorite.addedAt,
      viewCount: favorite.viewCount || 0,
      isPinned: favorite.isPinned || false,
      metadata: favorite.metadata || {}
    };
  }

  /**
   * Sort favorites list by priority and usage
   */
  sortFavorites() {
    this.favoritesList.sort((a, b) => {
      // Pinned items first
      if (a.isPinned !== b.isPinned) {
        return a.isPinned ? -1 : 1;
      }
      
      // Then by last viewed (most recent first)
      return (b.lastViewed || 0) - (a.lastViewed || 0);
    });
  }

  /**
   * Setup storage synchronization
   */
  setupStorageSync() {
    // Listen for storage events (cross-tab sync)
    if (typeof window !== 'undefined') {
      window.addEventListener('storage', (event) => {
        if (event.key === this.options.storageKey && event.newValue !== event.oldValue) {
          this.handleStorageSync(event.newValue);
        }
      });
    }
  }

  /**
   * Handle storage synchronization from other tabs
   * @param {string} newValue - New storage value
   */
  async handleStorageSync(newValue) {
    try {
      if (!newValue) return;
      
      const syncedFavorites = JSON.parse(newValue);
      if (!Array.isArray(syncedFavorites)) return;

      // Update local cache
      await this.loadFavorites();

      // Notify listeners of sync
      this.notifyListeners({
        type: 'sync',
        data: this.favoritesList,
        count: this.favoritesList.length,
        source: 'storage-sync'
      });

      if (FEATURES.DEBUG_MODE) {
        console.log('[FavoritesService] Synced from storage:', syncedFavorites.length, 'favorites');
      }

    } catch (error) {
      console.error('[FavoritesService] Storage sync failed:', error);
    }
  }

  /**
   * Subscribe to favorites changes
   * @param {Function} callback - Change callback
   * @returns {Function} - Unsubscribe function
   */
  subscribe(callback) {
    this.listeners.add(callback);
    
    return () => {
      this.listeners.delete(callback);
    };
  }

  /**
   * Notify change listeners
   * @param {FavoritesChangeEvent} event - Change event
   */
  notifyListeners(event) {
    this.listeners.forEach(callback => {
      try {
        callback(event);
      } catch (error) {
        console.error('[FavoritesService] Listener error:', error);
      }
    });
  }

  /**
   * Export favorites data
   * @returns {Object} - Exportable favorites data
   */
  exportData() {
    return {
      favorites: this.favoritesList,
      metrics: this.metrics,
      exportedAt: Date.now(),
      version: '1.0'
    };
  }

  /**
   * Import favorites data
   * @param {Object} data - Imported data
   * @returns {Promise<void>}
   */
  async importData(data) {
    if (!data || !Array.isArray(data.favorites)) {
      throw new AppError('Invalid import data', ERROR_TYPES.VALIDATION);
    }

    // Validate imported favorites
    const validFavorites = data.favorites.filter(favorite => 
      this.validateFavoriteLocation(favorite)
    );

    // Replace current favorites
    this.favorites.clear();
    this.favoritesList = [];

    validFavorites.forEach(favorite => {
      const normalized = this.normalizeFavoriteLocation(favorite);
      this.favorites.set(normalized.id, normalized);
      this.favoritesList.push(normalized);
    });

    this.sortFavorites();
    await this.saveFavorites();

    // Notify listeners
    this.notifyListeners({
      type: 'import',
      data: this.favoritesList,
      count: this.favoritesList.length,
      source: 'import'
    });

    if (FEATURES.DEBUG_MODE) {
      console.log('[FavoritesService] Imported', validFavorites.length, 'favorites');
    }
  }

  /**
   * Clear all favorites
   * @returns {Promise<void>}
   */
  async clear() {
    await this.ensureInitialized();

    const previousCount = this.favoritesList.length;
    
    this.favorites.clear();
    this.favoritesList = [];

    await this.saveFavorites();

    this.notifyListeners({
      type: 'clear',
      data: null,
      count: 0,
      source: 'FavoritesService.clear'
    });

    if (FEATURES.DEBUG_MODE) {
      console.log('[FavoritesService] Cleared', previousCount, 'favorites');
    }
  }

  /**
   * Get service statistics
   * @returns {Object} - Service statistics
   */
  getStats() {
    return {
      count: this.favoritesList.length,
      maxCount: this.options.maxFavorites,
      pinned: this.favoritesList.filter(f => f.isPinned).length,
      metrics: { ...this.metrics },
      countries: [...new Set(this.favoritesList.map(f => f.country))].length,
      mostViewed: this.favoritesList.reduce((max, current) => 
        (current.viewCount || 0) > (max.viewCount || 0) ? current : max, 
        this.favoritesList[0] || null
      )
    };
  }

  /**
   * Ensure service is initialized
   * @returns {Promise<void>}
   */
  async ensureInitialized() {
    if (!this.initialized && !this.initializing) {
      await this.initialize();
    }
    
    // Wait for initialization to complete if in progress
    while (this.initializing) {
      await new Promise(resolve => setTimeout(resolve, 10));
    }
  }

  /**
   * Destroy service and cleanup
   */
  destroy() {
    this.listeners.clear();
    this.favorites.clear();
    this.favoritesList = [];
    this.initialized = false;

    if (FEATURES.DEBUG_MODE) {
      console.log('[FavoritesService] Destroyed');
    }
  }
}

// Create singleton instance
export const favoritesService = new FavoritesService();

// Export convenience functions
export const addFavorite = (location, options) => favoritesService.add(location, options);
export const removeFavorite = (id) => favoritesService.remove(id);
export const getFavorite = (id) => favoritesService.get(id);
export const getAllFavorites = () => favoritesService.getAll();
export const isFavoriteLocation = (lat, lon) => favoritesService.isFavorite(lat, lon);
export const searchFavorites = (query) => favoritesService.search(query);

export default favoritesService;