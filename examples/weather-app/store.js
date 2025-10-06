// store.js

/**
 * State management for the weather application.
 * This module manages user input and fetched weather data.
 */

class Store {
  constructor() {
    this.state = {
      city: '',
      weatherData: null,
      loading: false,
      error: null,
    };
  }

  /**
   * Updates the city state.
   * @param {string} city - The new city to update.
   */
  setCity(city) {
    this.state.city = city;
  }

  /**
   * Updates the weather data state.
   * @param {Object} data - The weather data fetched from the API.
   */
  setWeatherData(data) {
    this.state.weatherData = data;
    this.state.loading = false; // Once data is set, loading stops
  }

  /**
   * Sets the loading state during data fetching.
   */
  setLoading() {
    this.state.loading = true;
    this.state.error = null; // Reset error state on loading
  }

  /**
   * Sets an error state when the fetch fails.
   * @param {string} error - The error message.
   */
  setError(error) {
    this.state.loading = false;
    this.state.error = error;
  }

  /**
   * Gets the current state.
   * @returns {Object} The current state of the application.
   */
  getState() {
    return this.state;
  }
}

export const store = new Store();