// src/services/api.js

const API_KEY = process.env.REACT_APP_API_KEY; // Replace with your actual OpenWeatherMap API key
const BASE_URL = 'https://api.openweathermap.org/data/2.5';

/**
 * Fetch current weather data by city name.
 *
 * @param {string} city - The name of the city to fetch weather data for.
 * @returns {Promise<Object>} The weather data for the specified city.
 */
export const fetchWeatherByCity = async (city) => {
    try {
        const response = await fetch(`${BASE_URL}/weather?q=${city}&appid=${API_KEY}&units=metric`);
        if (!response.ok) {
            throw new Error(`Error fetching weather data: ${response.statusText}`);
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Failed to fetch weather data:', error);
        throw error; // Rethrow the error for the calling function to handle
    }
};

/**
 * Fetch weather data by geographical coordinates.
 *
 * @param {number} lat - Latitude of the location.
 * @param {number} lon - Longitude of the location.
 * @returns {Promise<Object>} The weather data for the specified coordinates.
 */
export const fetchWeatherByCoordinates = async (lat, lon) => {
    try {
        const response = await fetch(`${BASE_URL}/weather?lat=${lat}&lon=${lon}&appid=${API_KEY}&units=metric`);
        if (!response.ok) {
            throw new Error(`Error fetching weather data: ${response.statusText}`);
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Failed to fetch weather data:', error);
        throw error; // Rethrow the error for the calling function to handle
    }
};