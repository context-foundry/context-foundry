// Actual complete code goes here
const API_KEY = 'c4b27d06b0817cd09f83aa58745fda97'; // Your OpenWeatherMap API Key
const BASE_URL = 'https://api.openweathermap.org/data/2.5/weather';

/**
 * Fetch weather data from OpenWeatherMap API based on city name.
 *
 * @param {string} city - The name of the city to fetch the weather for.
 * @returns {Promise<object>} The weather data for the specified city.
 */
async function fetchWeatherData(city) {
    try {
        const response = await fetch(`${BASE_URL}?q=${city}&appid=${API_KEY}&units=metric`);
        if (!response.ok) {
            throw new Error(`Error fetching weather data: ${response.statusText}`);
        }
        const data = await response.json();
        return extractWeatherData(data);
    } catch (error) {
        console.error(error);
        alert("Failed to fetch weather data. Please try again.");
    }
}

/**
 * Extract relevant data from API response.
 *
 * @param {object} data - The JSON response from the API.
 * @returns {object} An object containing extracted weather information.
 */
function extractWeatherData(data) {
    return {
        city: data.name,
        temperature: data.main.temp,
        description: data.weather[0].description,
        humidity: data.main.humidity,
        windSpeed: data.wind.speed,
    };
}

/**
 * Handle user input and fetch weather data.
 *
 * @param {Event} event - The event triggered by form submission.
 */
function handleUserInput(event) {
    event.preventDefault();
    const cityInput = document.getElementById('cityInput');
    const cityName = cityInput.value.trim();
    if (cityName) {
        fetchWeatherData(cityName).then((weatherData) => {
            if (weatherData) {
                displayWeatherData(weatherData);
            }
        });
        cityInput.value = ''; // Clear input field after submission
    } else {
        alert("Please enter a city name.");
    }
}

/**
 * Display fetched weather data to the user.
 *
 * @param {object} weatherData - The weather data to display.
 */
function displayWeatherData(weatherData) {
    const weatherInfoContainer = document.getElementById('weatherInfo');
    weatherInfoContainer.innerHTML = `
        <h3>Weather in ${weatherData.city}</h3>
        <p>Temperature: ${weatherData.temperature}°C</p>
        <p>Description: ${weatherData.description}</p>
        <p>Humidity: ${weatherData.humidity}%</p>
        <p>Wind Speed: ${weatherData.windSpeed} m/s</p>
    `;
}

// Add event listener for form submission
document.getElementById('weatherForm').addEventListener('submit', handleUserInput);