// API Integration to fetch weather data from OpenWeatherMap 

// OpenWeatherMap API Key
const API_KEY = 'YOUR_API_KEY'; // Replace with your actual API key

/**
 * Fetch weather data for a specified city from OpenWeatherMap API.
 * @param {string} city - The name of the city to fetch the weather for.
 * @returns {Promise<Object>} - A promise that resolves to the weather data.
 */
async function fetchWeather(city) {
    const url = `https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}&units=metric`;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error('City not found');
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching weather data:', error);
        throw error;
    }
}

/**
 * Handle the form submission to fetch the weather data.
 * @param {Event} event - The form submission event.
 */
function handleFormSubmit(event) {
    event.preventDefault();
    const cityInput = document.getElementById('cityInput');
    const city = cityInput.value.trim();

    if (city) {
        fetchWeather(city)
            .then(data => {
                displayWeather(data);
            })
            .catch(error => {
                alert(error.message);
            });
    } else {
        alert('Please enter a city name');
    }
}

/**
 * Display the fetched weather data on the webpage.
 * @param {Object} data - The weather data object.
 */
function displayWeather(data) {
    const weatherContainer = document.getElementById('weather');
    const { name, main, weather } = data;
    const weatherInfo = `
        <h2>Weather in ${name}</h2>
        <p>Temperature: ${main.temp} °C</p>
        <p>Condition: ${weather[0].description}</p>
    `;
    weatherContainer.innerHTML = weatherInfo;
}

// Event Listener for Form Submission
document.getElementById('weatherForm').addEventListener('submit', handleFormSubmit);