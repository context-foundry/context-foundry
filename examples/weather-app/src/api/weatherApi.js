import axios from "axios";

/**
 * Utility to interact with the OpenWeather API.
 * Includes methods for retrieving weather data.
 */
class WeatherApi {
  /**
   * @param {string} apiKey - The API key for OpenWeather.
   */
  constructor(apiKey) {
    if (!apiKey) {
      throw new Error("API key is required to create WeatherApi instance.");
    }
    this.apiKey = apiKey;
    this.baseUrl = "https://api.openweathermap.org/data/2.5";
  }

  /**
   * Fetch current weather for a given city.
   * @param {string} city - The city name.
   * @returns {Promise<object>} - Returns a Promise resolving to weather data.
   */
  async fetchCurrentWeather(city) {
    if (!city) {
      throw new Error("City name is required to fetch weather data.");
    }

    const url = `${this.baseUrl}/weather?q=${city}&appid=${this.apiKey}`;

    try {
      const response = await axios.get(url);
      return response.data;
    } catch (error) {
      console.error("Error fetching weather data:", error.message);
      throw new Error("Could not fetch weather data. Please try again.");
    }
  }

  /**
   * Convert temperature from Kelvin to Celsius.
   * @param {number} kelvin - Temperature in Kelvin.
   * @returns {number} - Temperature in Celsius.
   */
  static kelvinToCelsius(kelvin) {
    return (kelvin - 273.15).toFixed(2);
  }
}

export default WeatherApi;