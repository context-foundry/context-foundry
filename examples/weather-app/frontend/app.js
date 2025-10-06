// frontend/app.js
const API_KEY = 'YOUR_REAL_API_KEY'; // Replace with your actual API key

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('city-form');
    const cityInput = document.getElementById('city-input');
    const errorMessage = document.getElementById('error-message');

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        const cityName = cityInput.value.trim();

        if (validateCityName(cityName)) {
            errorMessage.textContent = '';
            fetchWeatherData(cityName);
        } else {
            errorMessage.textContent = 'Please enter a valid city name.';
        }
    });
});

// Validates that the city name is not empty and only contains letters and spaces
function validateCityName(cityName) {
    const regex = /^[A-Za-z\s]+$/;
    return regex.test(cityName) && cityName.length > 0;
}

// Fetch weather data from the API
async function fetchWeatherData(cityName) {
    const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${cityName}&appid=${API_KEY}`);
    if (!response.ok) {
        console.error('Error fetching weather data:', response.statusText);
        return;
    }
    const data = await response.json();
    // Process and display the weather data
    console.log(data); // For example purposes
}