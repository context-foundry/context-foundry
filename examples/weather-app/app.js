// app.js

// Function to display weather information
function displayWeather(data) {
    const weatherDisplay = document.getElementById('weatherDisplay');
    weatherDisplay.innerHTML = `
        <h2>Weather in ${data.name}</h2>
        <p>Temperature: ${(data.main.temp - 273.15).toFixed(2)} °C</p>
        <p>Weather: ${data.weather[0].description}</p>
    `;
}

// Function to display error notification
function displayError(message) {
    const errorNotification = document.getElementById('errorNotification');
    errorNotification.innerText = message;
}

// Function to fetch weather data
async function fetchWeather(city) {
    const API_KEY = 'YOUR_API_KEY'; // Replace with actual API key
    const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}`);

    if (!response.ok) {
        displayError('City not found. Please try again.');
        return;
    }

    const data = await response.json();
    displayWeather(data);
}

// Event listener for the search button
document.getElementById('searchButton').addEventListener('click', () => {
    const cityInput = document.getElementById('cityInput').value;
    if (cityInput) {
        displayError(''); // Clear previous errors
        fetchWeather(cityInput);
    } else {
        displayError('Please enter a city name.');
    }
});