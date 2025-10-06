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
  card.className = "mt-4 p-6 bg-white rounded-lg shadow-md max-w-md mx-auto";

  const loadingText = document.createElement("p");
  loadingText.className = "text-gray-600";
  loadingText.innerText = "Fetching weather data...";
  card.appendChild(loadingText);

  try {
    const weatherData = await weatherApi.fetchCurrentWeather(city);

    // Clear previous content in the card to update it with fetched weather data
    card.innerHTML = "";

    const cityTitle = document.createElement("h2");
    cityTitle.className = "text-xl font-bold text-center mb-2";
    cityTitle.innerText = `Weather in ${city}`;
    card.appendChild(cityTitle);

    const weatherDescription = document.createElement("p");
    weatherDescription.className = "text-gray-800 text-center";
    weatherDescription.innerText = weatherData.weather[0].description;
    card.appendChild(weatherDescription);

    const temperature = document.createElement("p");
    temperature.className = "text-lg text-gray-800 font-semibold text-center";
    temperature.innerText = `Temperature: ${WeatherApi.kelvinToCelsius(
      weatherData.main.temp
    )} °C`;
    card.appendChild(temperature);

    const humidity = document.createElement("p");
    humidity.className = "text-gray-700 text-center";
    humidity.innerText = `Humidity: ${weatherData.main.humidity}%`;
    card.appendChild(humidity);
  } catch (error) {
    console.error("Error creating WeatherCard:", error.message);
    card.innerHTML = `
      <p class="text-red-500 text-center">Failed to fetch weather data. Try again later.</p>
    `;
  }

  return card;
}

export default WeatherCard;