// src/services/weatherService.js
import axios from 'axios';

const API_KEY = 'YOUR_API_KEY'; // Replace with your OpenWeatherMap API key
const BASE_URL = 'https://api.openweathermap.org/data/2.5/weather';

/**
 * Gets weather data for a specific city.
 * 
 * @param {string} city - The city to fetch the weather for.
 * @returns {Promise<object>} - The weather data.
 * @throws {Error} - Throws an error if the request fails or if the city is not found.
 */
export const getWeatherByCity = async (city) => {
    try {
        const response = await axios.get(BASE_URL, {
            params: {
                q: city,
                appid: API_KEY,
                units: 'metric', // Use 'imperial' for Fahrenheit
            },
        });

        if (response.status !== 200) {
            throw new Error(`Error: ${response.status} - ${response.statusText}`);
        }

        return response.data;
    } catch (error) {
        if (error.response) {
            // Received a response with an error status
            throw new Error(`Error: ${error.response.status} - ${error.response.data.message}`);
        } else if (error.request) {
            // No response was received
            throw new Error('Error: No response received from the weather service.');
        } else {
            // Something happened while setting up the request
            throw new Error(`Error: ${error.message}`);
        }
    }
};