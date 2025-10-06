// app.js - Main application file

import { getWeatherData } from './api.js';
import { renderWeatherData } from './store.js';

/**
 * Initializes the application
 */
function init() {
    document.getElementById('searchButton').addEventListener('click', handleSearch);
}

/**
 * Handles the search for weather data
 */
async function handleSearch() {
    const city = document.getElementById('cityInput').value;
    const weatherData = await getWeatherData(city);
    renderWeatherData(weatherData);
}

window.onload = init;