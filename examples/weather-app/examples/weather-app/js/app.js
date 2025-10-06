// JavaScript for Weather App

/**
 * Fetch weather data for the given city
 * @param {string} city The name of the city to fetch weather for
 */
async function fetchWeather(city) {
    try {
        const apiKey = 'YOUR_API_KEY_HERE'; // Replace with an actual API key from a weather service
        const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${apiKey}&units=metric`);
        const data = await response.json();

        if (response.ok) {
            displayWeather(data);
        } else {
            alert(data.message || 'Unable to fetch weather data.');
        }
    } catch (error) {
        console.error('Error fetching weather data:', error);
        alert('An error occurred while fetching weather data.');
    }
}

/**
 * Display the fetched weather data on the page
 * @param {Object} data The weather data returned from API
 */
function displayWeather(data) {
    const weatherInfo = document.getElementById('weather-info');
    const locationName = document.getElementById('location-name');
    const temperature = document.getElementById('temperature');
    const description = document.getElementById('description');

    locationName.textContent = `Location: ${data.name}, ${data.sys.country}`;
    temperature.textContent = `Temperature: ${data.main.temp} °C`;
    description.textContent = `Description: ${data.weather[0].description}`;

    weatherInfo.classList.remove('hidden');
}

// Event listener for the search button
document.getElementById('search-button').addEventListener('click', () => {
    const city = document.getElementById('city-input').value.trim();
    if (city) {
        fetchWeather(city);
    } else {
        alert('Please enter a city name.');
    }
});