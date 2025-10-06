import axios from 'axios';

// Replace with your actual API key
const API_KEY = process.env.REACT_APP_WEATHER_API_KEY;

/**
 * Fetch weather data from OpenWeatherMap API based on the city name.
 *
 * @param {string} city - The name of the city to fetch weather data for.
 * @returns {Promise} - A promise that resolves to the weather data.
 */
export const fetchWeatherData = async (city) => {
    if (!city) {
        throw new Error("City name is required");
    }

    const url = `https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}&units=metric`; // Use metric for Celsius

    try {
        const response = await axios.get(url);
        return response.data;
    } catch (error) {
        throw new Error("Error fetching weather data: " + error.message);
    }
};