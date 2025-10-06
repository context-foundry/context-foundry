import { fetchWeatherData, parseWeatherData } from "./utils.js";

/**
 * Application logic for the Weather App
 * Handles user interactions and API error handling
 */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("weather-form");
  const cityInput = document.getElementById("city-input");
  const resultContainer = document.getElementById("result");
  const errorContainer = document.getElementById("error-message");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const city = cityInput.value.trim();
    if (!city) {
      showError("City name cannot be empty.");
      return;
    }

    // Clear previous results and errors
    resultContainer.innerHTML = "";
    errorContainer.innerHTML = "";

    const apiURL = `https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=YOUR_API_KEY&units=metric`;

    try {
      const data = await fetchWeatherData(apiURL);
      const parsedData = parseWeatherData(data);
      renderWeather(parsedData);
    } catch (error) {
      showError(error.message);
    }
  });

  /**
   * Render weather information on the page
   * @param {Object} weather - The weather data object
   */
  function renderWeather(weather) {
    const { city, temp, temp_min, temp_max } = weather;
    resultContainer.innerHTML = `
      <p><strong>${city}</strong></p>
      <p>Temperature: ${temp} &#8451;</p>
      <p>Min Temperature: ${temp_min} &#8451;</p>
      <p>Max Temperature: ${temp_max} &#8451;</p>`;
  }

  /**
   * Display error message to the user
   * @param {string} message - Error message to display
   */
  function showError(message) {
    errorContainer.innerHTML = `<p class="error">${message}</p>`;
  }
});