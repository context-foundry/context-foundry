/**
 * Global State Management for the Weather App.
 * This store holds application-wide state and provides methods to interact
 * and modify the state.
 */

// Initial state object
const state = {
  city: "London", // Default city
  weatherData: null, // Initial weather data to be fetched
};

/**
 * Subscribers to listen for state changes.
 * @type {Set<Function>}
 */
const subscribers = new Set();

/**
 * Notify all subscribers of the state update.
 */
function notifySubscribers() {
  subscribers.forEach((subscriber) => subscriber(state));
}

/**
 * Get the current state.
 * @returns {object} - The current state object.
 */
export function getState() {
  return { ...state };
}

/**
 * Update the state and notify components.
 * @param {object} newState - An object defining keys to update in the state.
 */
export function updateState(newState) {
  Object.assign(state, newState);
  notifySubscribers();
}

/**
 * Subscribe to state changes.
 * @param {Function} callback - The callback function to listen to state updates.
 * @returns {Function} - A function to unsubscribe the given callback.
 */
export function subscribe(callback) {
  subscribers.add(callback);

  // Return an unsubscribe function
  return () => subscribers.delete(callback);
}