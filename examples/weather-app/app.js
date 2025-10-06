// Weather app script to fetch weather data and handle user input

const API_KEY = 'YOUR_API_KEY'; // Replace with actual API Key
const weatherForm = document.getElementById('weather-form');
const searchInput = document.getElementById('search-input');
const weatherOutput = document.getElementById('weather-output');
const errorMessage = document.getElementById('error-message');

weatherForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    
    const location = searchInput.value.trim();
    
    // Validate user input
    if (!location) {
        displayError('Please enter a valid location.');
        return;
    }
    
    try {
        // Fetch weather data from API
        const response = await fetch(`https://api.weatherapi.com/v1/current.json?key=${API_KEY}&q=${encodeURIComponent(location)}`);
        
        if (!response.ok) {
            throw new Error('City not found. Please try again.');
        }
        
        const data = await response.json();
        displayWeather(data);
        errorMessage.textContent = ''; // Clear any previous error messages
    } catch (error) {
        displayError(error.message);
    }
});

// Function to display weather information
function displayWeather(data) {
    const { location, current } = data;
    weatherOutput.innerHTML = `
        <h2>Weather in ${location.name}, ${location.country}</h2>
        <p>Temperature: ${current.temp_c}°C</p>
        <p>Condition: ${current.condition.text}</p>
        <img src="${current.condition.icon}" alt="${current.condition.text}" />
    `;
}

// Function to display error messages
function displayError(message) {
    errorMessage.textContent = message;
    weatherOutput.innerHTML = ''; // Clear previous weather output
}