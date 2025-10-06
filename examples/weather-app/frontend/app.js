// Initialize OpenWeatherMap API key and base URL
const API_KEY = 'YOUR_API_KEY'; // Replace with your actual OpenWeatherMap API key
const BASE_URL = 'https://api.openweathermap.org/data/2.5/weather';

/**
 * Fetch weather data for a specific city.
 * @param {string} city - The name of the city to fetch weather data for.
 * @returns {Promise<Object>} - A promise that resolves to the weather data.
 */
async function fetchWeatherData(city) {
    const url = `${BASE_URL}?q=${city}&appid=${API_KEY}&units=metric`;
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error('Network response was not ok ' + response.statusText);
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('There has been a problem with your fetch operation:', error);
    }
}

/**
 * Display weather data on the page.
 * @param {Object} data - The weather data object returned by the fetchWeatherData function.
 */
function displayWeather(data) {
    const weatherContainer = document.getElementById('weather-container');
    if (data && data.main) {
        const temperature = data.main.temp;
        const description = data.weather[0].description;
        const cityName = data.name;
        weatherContainer.innerHTML = `
            <h2>Weather in ${cityName}</h2>
            <p>Temperature: ${temperature} °C</p>
            <p>Description: ${description}</p>
        `;
    } else {
        weatherContainer.innerHTML = `<p>Weather data not available.</p>`;
    }
}

// Event listener for form submission to fetch weather data
document.getElementById('search-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const city = document.getElementById('city-input').value;
    const weatherData = await fetchWeatherData(city);
    displayWeather(weatherData);
});