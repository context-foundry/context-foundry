// app.js

const API_KEY = 'your_actual_api_key'; // Replace with your actual API key
const weatherForm = document.getElementById('weather-form');
const weatherOutput = document.getElementById('weather-output');

weatherForm.addEventListener('submit', (event) => {
    event.preventDefault(); // Prevent form submission
    const city = event.target.elements.city.value;
    fetchWeatherData(city);
});

/**
 * Fetch weather data from the OpenWeather API.
 * @param {string} city - The name of the city to fetch weather data for.
 */
async function fetchWeatherData(city) {
    try {
        const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}&units=metric`);
        if (!response.ok) {
            throw new Error('City not found');
        }
        const data = await response.json();
        displayWeatherData(data);
    } catch (error) {
        displayError(error.message);
    }
}

/**
 * Display weather data in the HTML.
 * @param {Object} data - The JSON data retrieved from the weather API.
 */
function displayWeatherData(data) {
    const { name, main, weather } = data;
    weatherOutput.innerHTML = `
        <h2>Weather in ${name}</h2>
        <p>Temperature: ${main.temp} °C</p>
        <p>Condition: ${weather[0].description}</p>
    `;
}

/**
 * Display an error message in the HTML.
 * @param {string} message - The error message to display.
 */
function displayError(message) {
    weatherOutput.innerHTML = `<p class="error">${message}</p>`;
}