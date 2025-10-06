import axios from 'axios';

/**
 * Fetch weather data from OpenWeatherMap API.
 * @param {string} city - The name of the city to fetch the weather for.
 * @returns {Promise<object>} - A promise that resolves to the weather data object.
 * @throws {Error} - An error if the fetch operation fails or if the API returns an error.
 */
export const fetchWeatherData = async (city) => {
    const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Ensure your API key is stored in .env file

    const url = `https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}&units=metric`;
    
    try {
        const response = await axios.get(url);

        // Handle success response
        if (response.status === 200) {
            return response.data;
        } else {
            throw new Error('Failed to fetch weather data');
        }
    } catch (error) {
        // Handle errors (network errors, response status not 200 etc.)
        throw new Error(error.response?.data?.message || 'Something went wrong!');
    }
};