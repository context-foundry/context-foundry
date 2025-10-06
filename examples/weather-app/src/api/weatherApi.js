// This module handles the API calls to fetch current weather and forecast data from OpenWeatherMap.

const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Ensure to set this in your .env file
const BASE_URL = 'https://api.openweathermap.org/data/2.5';

/**
 * Fetch current weather data for a given city.
 * @param {string} cityName - The name of the city to fetch weather data for.
 * @returns {Promise<object>} - A promise that resolves to the current weather data.
 */
export const fetchCurrentWeather = async (cityName) => {
    try {
        const response = await fetch(`${BASE_URL}/weather?q=${cityName}&appid=${API_KEY}&units=metric`);
        if (!response.ok) {
            throw new Error('Unable to fetch current weather data.');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        throw error;
    }
};

/**
 * Fetch forecast weather data for a given city.
 * @param {string} cityName - The name of the city to fetch forecast data for.
 * @returns {Promise<object>} - A promise that resolves to the forecast weather data.
 */
export const fetchWeatherForecast = async (cityName) => {
    try {
        const response = await fetch(`${BASE_URL}/forecast?q=${cityName}&appid=${API_KEY}&units=metric`);
        if (!response.ok) {
            throw new Error('Unable to fetch weather forecast data.');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        throw error;
    }
};