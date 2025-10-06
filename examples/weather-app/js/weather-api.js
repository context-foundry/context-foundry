/**
 * File: js/weather-api.js
 * Description: Weather API Module to fetch and handle weather data.
 */

/**
 * Fetches weather data from the OpenWeatherMap API.
 *
 * @param {string} city - Name of the city to fetch the weather for.
 * @returns {Promise<Object>} - Returns a Promise resolving to weather data object.
 * @throws {Error} - Throws error if the API request fails.
 */
export async function fetchWeatherData(city) {
  const apiKey = "YOUR_API_KEY"; // Replace with your actual API key
  const endpoint = `https://api.openweathermap.org/data/2.5/weather?q=${encodeURIComponent(city)}&appid=${apiKey}&units=metric`;

  try {
    const response = await fetch(endpoint);

    if (!response.ok) {
      throw new Error(`Error fetching weather data: ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error("API Fetch Error:", error);
    throw error;
  }
}

/**
 * Extracts and processes relevant weather information.
 *
 * @param {Object} data - Raw weather data from API.
 * @returns {Object} - Processed weather information for display.
 */
export function processWeatherData(data) {
  return {
    cityName: data.name,
    temperature: data.main.temp,
    feelsLike: data.main.feels_like,
    weatherDescription: data.weather[0]?.description,
    windSpeed: data.wind.speed,
    humidity: data.main.humidity,
    icon: data.weather[0]?.icon,
  };
}

/**
 * Constructs the icon URL based on the icon code from the API.
 *
 * @param {string} iconCode - Icon code from weather data.
 * @returns {string} - URL for the weather icon.
 */
export function getWeatherIconUrl(iconCode) {
  return `https://openweathermap.org/img/wn/${iconCode}@2x.png`;
}