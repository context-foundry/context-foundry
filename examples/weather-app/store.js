// store.js - Module to render weather data

/**
 * Renders weather data on the page
 * @param {Object} weatherData - Weather data to render
 */
export function renderWeatherData(weatherData) {
    const outputElement = document.getElementById('output');
    outputElement.innerHTML = `
        <h2>${weatherData.name}</h2>
        <p>Temperature: ${weatherData.main.temp}°C</p>
        <p>Weather: ${weatherData.weather[0].description}</p>
    `;
}