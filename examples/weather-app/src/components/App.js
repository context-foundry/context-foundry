import Header from "./Header";
import WeatherCard from "./WeatherCard";
import CitySelector from "./CitySelector";
import WeatherApi from "../api/weatherApi";
import { getState, subscribe } from "../state/store";

const weatherApi = new WeatherApi("YOUR_API_KEY"); // Replace with an actual API key

/**
 * App component for the Weather App.
 * Renders the header, city selector, and weather card.
 */
function App() {
  const app = document.getElementById("app");
  app.innerHTML = ""; // Clear contents

  const header = Header();
  const weatherContainer = document.createElement("div"); // Section for Weather Card
  weatherContainer.className = "pt-4";

  const state = getState();

  // Function to update the weather card based on the selected city
  async function updateWeatherCard(city) {
    const weatherCard = await WeatherCard(city, weatherApi);
    weatherContainer.innerHTML = ""; // Clear previous card
    weatherContainer.appendChild(weatherCard);
  }

  const citySelector = CitySelector(async (city) => {
    updateWeatherCard(city); // Fetch new weather data when city changes
  });

  app.appendChild(header);
  app.appendChild(citySelector);
  app.appendChild(weatherContainer);

  // Subscribe to global state changes
  subscribe(({ city }) => {
    updateWeatherCard(city); // Update the weather card when state changes
  });

  updateWeatherCard(state.city); // Render initial weather card
}

export default App;