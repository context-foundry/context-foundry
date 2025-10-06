// Actual complete code goes here
const API_KEY = 'YOUR_ACTUAL_API_KEY_HERE'; // Replace with your actual API key
const weatherApiUrl = 'https://api.openweathermap.org/data/2.5/weather';

async function fetchWeather(city) {
    const response = await fetch(`${weatherApiUrl}?q=${city}&appid=${API_KEY}&units=metric`);
    
    if (!response.ok) {
        throw new Error('City not found');
    }

    return await response.json();
}

function updateDOM(data) {
    const weatherContainer = document.getElementById('weather-info');
    const errorContainer = document.getElementById('error-message');

    // Clear previous error message
    errorContainer.textContent = '';

    // Create HTML for weather data
    const { name, main: { temp, feels_like }, weather } = data;
    const weatherDescription = weather[0].description;

    weatherContainer.innerHTML = `
      <h2>Weather in ${name}</h2>
      <p>Temperature: ${temp} °C</p>
      <p>Feels like: ${feels_like} °C</p>
      <p>Description: ${weatherDescription}</p>
    `;
}

function handleError(error) {
    const errorContainer = document.getElementById('error-message');
    errorContainer.textContent = error.message;
}

document.getElementById('search-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const cityInput = document.getElementById('city-input').value;

    try {
        const weatherData = await fetchWeather(cityInput);
        updateDOM(weatherData);
    } catch (error) {
        handleError(error);
    }
});