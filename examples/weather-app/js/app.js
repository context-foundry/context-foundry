// Define constants for API integration and DOM interaction
const API_KEY = 'your_api_key_here'; // Replace with your actual API key
const BASE_URL = 'https://api.openweathermap.org/data/2.5/weather';

/**
 * Fetch weather data for a given city.
 *
 * @param {string} city - Name of the city to fetch weather for.
 * @returns {Promise<object>} - A promise resolving to the data object from the API.
 */
async function fetchWeatherData(city) {
  try {
    const response = await fetch(`${BASE_URL}?q=${city}&appid=${API_KEY}&units=metric`);
    if (!response.ok) {
      throw new Error('City not found');
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching weather data:', error.message);
    throw error;
  }
}

/**
 * Updates the weather results section with data from the API.
 *
 * @param {object} data - Weather data returned from the API.
 */
function updateWeatherUI(data) {
  const weatherSection = document.getElementById('weather-results');

  // Clear previous data
  weatherSection.innerHTML = '';

  // Create and insert dynamic UI elements
  const city = document.createElement('h2');
  city.textContent = `${data.name}, ${data.sys.country}`;
  const temperature = document.createElement('p');
  temperature.textContent = `Temperature: ${data.main.temp}°C`;
  const weatherDescription = document.createElement('p');
  weatherDescription.textContent = `Condition: ${data.weather[0].description}`;
  const humidity = document.createElement('p');
  humidity.textContent = `Humidity: ${data.main.humidity}%`;

  // Append elements to UI
  weatherSection.appendChild(city);
  weatherSection.appendChild(temperature);
  weatherSection.appendChild(weatherDescription);
  weatherSection.appendChild(humidity);
}

/**
 * Handles the search button click event.
 */
async function handleSearch() {
  const inputField = document.getElementById('location-input');
  const city = inputField.value.trim();

  if (!city) {
    alert('Please enter a city name.');
    return;
  }

  try {
    const weatherData = await fetchWeatherData(city);
    updateWeatherUI(weatherData);
  } catch (error) {
    alert('Could not fetch weather data. Please try again.');
  }
}

// Event listener for search button
document.getElementById('search-btn').addEventListener('click', handleSearch);