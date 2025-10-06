/**
 * Fetch weather data from OpenWeatherMap API.
 * @param {string} city - The name of the city to fetch weather data for.
 * @returns {Promise<void>}
 */
async function fetchWeather(city) {
    const API_KEY = 'your_actual_api_key'; // Replace with your OpenWeatherMap API key
    const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}&units=metric`);
    const data = await response.json();
    return data;
}

/**
 * Display weather result on the webpage.
 * @param {string} city - The name of the city.
 * @param {object} weatherData - The weather data object.
 */
function displayWeather(city, weatherData) {
    const weatherResult = document.getElementById('weatherResult');
    if (weatherData.cod === 200) {
        const description = weatherData.weather[0].description;
        const temperature = weatherData.main.temp;
        weatherResult.innerHTML = `<h2>Weather in ${city}</h2><p>${description}</p><p>Temperature: ${temperature}°C</p>`;
    } else {
        weatherResult.innerHTML = `<p>${weatherData.message}</p>`;
    }
}

// Event listener for the button click
document.getElementById('getWeather').addEventListener('click', async () => {
    const cityInput = document.getElementById('city').value;
    if (cityInput) {
        const weatherData = await fetchWeather(cityInput);
        displayWeather(cityInput, weatherData);
    } else {
        alert('Please enter a city name!');
    }
});