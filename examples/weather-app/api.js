// api.js - API module to fetch weather data

const API_KEY = 'YOUR_API_KEY'; // Replace with your actual API key
const BASE_URL = 'https://api.openweathermap.org/data/2.5/weather';

/**
 * Fetches weather data for a given city
 * @param {string} city - Name of the city
 * @returns {Promise<Object>} - Weather data
 */
export async function getWeatherData(city) {
    const response = await fetch(`${BASE_URL}?q=${city}&appid=${API_KEY}&units=metric`);
    if (!response.ok) {
        throw new Error('Unable to fetch weather data');
    }
    return response.json();
}