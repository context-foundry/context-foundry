import WeatherApi from "../api/weatherApi";

/**
 * WeatherCard component for displaying weather details of a city.
 * 
 * @param {string} city - The name of the city to display the weather for.
 * @param {WeatherApi} weatherApi - The WeatherApi instance to fetch weather data.
 * @returns {HTMLElement} - The DOM element for the weather card.
 */
async function WeatherCard(city, weatherApi) {
  const card = document.createElement("div");
  card.className =
    "p-6 bg-white rounded-lg shadow-md max-w-md mx-auto mt-4 border border-gray-200";

  const loadingText = document.createElement("p");
  loadingText.className = "text-gray-500";
  loadingText.innerText = "Fetching weather data...";
  card.appendChild(loadingText);

  try {
    const weatherData = await weatherApi.fetchCurrentWeather(city);

    // Clear previous content in the card to update it with fetched weather data
    card.innerHTML = "";

    const cityTitle = document.createElement("h2");
    cityTitle.className = "text-xl font-semibold text-center text-gray-800 mb-3";
    cityTitle.innerText = `Weather in ${city}`;
    card.appendChild(cityTitle);

    const weatherDescription = document.createElement("p");
    weatherDescription.className = "text-lg text-gray-700 text-center";
    weatherDescription.innerText = weatherData.weather[0].description;
    card.appendChild(weatherDescription);

    const temperature = document.createElement("p");
    temperature.className = "text-lg text-gray-800 font-bold text-center my-2";
    temperature.innerText = `Temperature: ${WeatherApi.kelvinToCelsius(
      weatherData.main.temp
    )} °C`;
    card.appendChild(temperature);

    const humidity = document.createElement("p");
    humidity.className = "text-sm text-gray-600 text-center";
    humidity.innerText = `Humidity: ${weatherData.main.humidity}%`;
    card.appendChild(humidity);
  } catch (error) {
    console.error("Error creating WeatherCard:", error.message);
    card.innerHTML = `
      <p class="text-red-500 text-center">Failed to fetch weather data. Please try again.</p>
    `;
  }

  return card;
}

export default WeatherCard;