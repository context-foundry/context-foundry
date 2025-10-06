// Sample JavaScript code to dynamically update weather information
const weatherCard = document.getElementById('weather-card');

function updateWeather() {
    // Simulating fetching weather data (this should ideally be an API call)
    const weatherData = {
        temperature: '20°C',
        condition: 'Sunny'
    };

    document.getElementById('temperature').textContent = `Temp: ${weatherData.temperature}`;
    document.getElementById('condition').textContent = `Condition: ${weatherData.condition}`;
}

// Initial load
updateWeather();