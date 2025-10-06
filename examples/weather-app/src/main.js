import axios from "axios";

const weatherContainer = document.getElementById("weather-container");

/**
 * Fetch weather data from the OpenWeather API
 * @async
 */
async function fetchWeather() {
  const apiKey = "YOUR_API_KEY"; // Replace with your OpenWeather API key
  const city = "London"; // Example city
  const apiUrl = `https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${apiKey}`;

  try {
    const response = await axios.get(apiUrl);
    const { weather, main } = response.data;

    // Dynamically update the weather information
    weatherContainer.innerHTML = `
      <h2>Weather in ${city}</h2>
      <p>${weather[0].description}</p>
      <p>Temperature: ${(main.temp - 273.15).toFixed(2)} °C</p>
      <p>Humidity: ${main.humidity}%</p>
    `;
  } catch (error) {
    console.error("Error fetching weather data:", error);
    weatherContainer.innerHTML = `
      <p>Error fetching weather data. Please try again later.</p>
    `;
  }
}

// Initialize fetchWeather on page load
fetchWeather();