/**
 * Utility functions for the Weather App. Includes helper methods for API calls and error handling.
 */

/**
 * Fetch weather data from the API
 * @param {string} url - The API endpoint
 * @returns {Promise<Object>} - The weather data object
 * @throws {Error} - Throws error if response is not ok or fetch fails
 */
export async function fetchWeatherData(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error fetching weather data:", error);
    throw error; // Propagate the error to be handled by the caller
  }
}

/**
 * Parse weather data and handle exceptions during data access.
 * @param {Object} data - The weather data object received from the API
 * @returns {Object} - Parsed weather information
 * @throws {Error} - Throws error if data structure is invalid
 */
export function parseWeatherData(data) {
  try {
    if (!data || typeof data !== "object") {
      throw new Error("Invalid weather data: Data is undefined or not an object");
    }

    const { name: city, main: { temp, temp_min, temp_max } } = data;

    if (!city || temp === undefined || temp_min === undefined || temp_max === undefined) {
      throw new Error("Incomplete weather data: Missing expected fields");
    }

    return { city, temp, temp_min, temp_max };
  } catch (error) {
    console.error("Error parsing weather data:", error);
    throw error; // Propagate error to be handled by the caller
  }
}