import axios from 'axios';

const API_KEY = process.env.REACT_APP_WEATHER_API_KEY;
const BASE_URL = 'https://api.openweathermap.org/data/2.5/weather';

/**
 * Fetch weather data from OpenWeatherMap API
 * @param {string} city The name of the city to fetch weather for
 * @returns {Promise<Object>} The weather data
 * @throws {Error} Throws error if the API request fails
 */
export const fetchWeatherData = async (city) => {
    try {
        const response = await axios.get(`${BASE_URL}?q=${city}&appid=${API_KEY}&units=metric`);
        return response.data;
    } catch (error) {
        // Handle specific error responses
        if (error.response) {
            throw new Error(`Error ${error.response.status}: ${error.response.data.message}`);
        } else if (error.request) {
            throw new Error('Network error. Please try again later.');
        } else {
            throw new Error('An unexpected error occurred');
        }
    }
};