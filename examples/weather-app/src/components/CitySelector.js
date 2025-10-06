import { getState, updateState, subscribe } from "../state/store";

/**
 * CitySelector Component.
 * Allows users to select a city and fetch weather data.
 *
 * @param {Function} onCitySelected - Callback when city is selected.
 * @returns {HTMLElement} - The CitySelector DOM element.
 */
function CitySelector(onCitySelected) {
  const container = document.createElement("div");
  container.className = "mx-auto max-w-md flex justify-center items-center mt-6";

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Enter city name";
  input.className =
    "p-2 border rounded-lg shadow-sm focus:outline-none focus:border-primary w-2/3";
  container.appendChild(input);

  const button = document.createElement("button");
  button.className =
    "ml-2 p-2 bg-primary text-white font-bold rounded-lg shadow hover:bg-primary-dark";
  button.innerText = "Search";
  container.appendChild(button);

  button.addEventListener("click", () => {
    const city = input.value.trim();
    if (city) {
      updateState({ city }); // Update global state with the new city
      if (onCitySelected) {
        onCitySelected(city); // Notify parent or other components
      }
    }
  });

  return container;
}

export default CitySelector;