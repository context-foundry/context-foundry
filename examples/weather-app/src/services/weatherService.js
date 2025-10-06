import axios from 'axios';

const API_KEY = process.env.REACT_APP_WEATHER_API_KEY;  // Make sure to set this in your environment variables
const BASE_URL = 'https://api.openweathermap.org/data/2.5/';

const weatherService = {
  /**
   * Fetches the weather data for a specific city.
   * @param {string} city - The name of the city to fetch the weather for.
   * @returns {Promise} - A promise that resolves to the weather data.
   */
  getWeatherByCity: async (city) => {
    try {
      const response = await axios.get(`${BASE_URL}weather`, {
        params: {
          q: city,
          appid: API_KEY,
          units: 'metric', // You can change to 'imperial' for Fahrenheit
        }
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching weather data: ', error);
      throw error;
    }
  },

  /**
   * Fetches the 5-day weather forecast for a specific city.
   * @param {string} city - The name of the city to fetch the forecast for.
   * @returns {Promise} - A promise that resolves to the forecast data.
   */
  getForecastByCity: async (city) => {
    try {
      const response = await axios.get(`${BASE_URL}forecast`, {
        params: {
          q: city,
          appid: API_KEY,
          units: 'metric', // You can change to 'imperial' for Fahrenheit
        }
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching forecast data: ', error);
      throw error;
    }
  }
};

export default weatherService;