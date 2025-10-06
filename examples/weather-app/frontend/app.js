// API key for weather API
const API_KEY = 'your_actual_api_key_here'; // Replace with your actual API key

document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('.city-input form');
    const weatherContainer = document.querySelector('.weather-container');

    if (form) {
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            const city = form.elements.city.value;
            fetchWeather(city);
        });
    }
});

async function fetchWeather(city) {
    try {
        const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}&units=metric`);
        if (!response.ok) {
            throw new Error('City not found');
        }
        const data = await response.json();
        displayWeather(data);
    } catch (error) {
        alert(error.message);
    }
}

function displayWeather(data) {
    const weatherContainer = document.querySelector('.weather-container');

    const temperature = Math.round(data.main.temp);
    const weatherDescription = data.weather[0].description;
    const cityName = data.name;

    const weatherHTML = `
        <h1>Weather in ${cityName}</h1>
        <p>Temperature: ${temperature}°C</p>
        <p>Description: ${weatherDescription}</p>
    `;

    weatherContainer.innerHTML = weatherHTML;
}