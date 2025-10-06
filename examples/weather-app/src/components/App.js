import Header from "./Header";
import WeatherCard from "./WeatherCard";
import WeatherApi from "../api/weatherApi";

/**
 * App component for the Weather App.
 * Initializes the application and renders the header and weather card.
 */
function App() {
  const app = document.getElementById("app");
  app.innerHTML = ""; // Clear contents

  // Add Header
  const header = Header();
  app.appendChild(header);

  // Add WeatherCard
  const weatherApi = new WeatherApi("YOUR_API_KEY"); // Replace with actual API Key
  const city = "London"; // Default city
  WeatherCard(city, weatherApi).then((weatherCard) => {
    app.appendChild(weatherCard);
  });
}

export default App;