// Basic functionality for the Weather App

document.getElementById('getWeatherBtn').addEventListener('click', getWeather);

async function getWeather() {
    const city = document.getElementById('cityInput').value;
    const API_KEY = 'your_actual_api_key_here'; // Replace with your actual API key
    const apiUrl = `https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}&units=metric`;

    try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
            throw new Error('City not found');
        }
        const data = await response.json();
        displayWeather(data);
    } catch (error) {
        document.getElementById('weatherResult').innerText = error.message;
    }
}

function displayWeather(data) {
    const weatherResultDiv = document.getElementById('weatherResult');
    const temperature = data.main.temp;
    const description = data.weather[0].description;
    weatherResultDiv.innerHTML = `
        <h2>${data.name}</h2>
        <p>Temperature: ${temperature} °C</p>
        <p>Condition: ${description}</p>
    `;
}