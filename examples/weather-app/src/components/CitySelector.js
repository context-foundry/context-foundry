import { updateState } from "../state/store";

/**
 * CitySelector Component.
 * Allows users to select a city and fetch weather data.
 *
 * @returns {HTMLElement} - The CitySelector DOM element.
 */
function CitySelector() {
  const container = document.createElement("div");
  container.className =
    "flex justify-center items-center space-x-4 p-4 bg-gray-100 rounded-md shadow-lg";

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Enter city name";
  input.className =
    "p-2 w-2/3 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500";
  container.appendChild(input);

  const button = document.createElement("button");
  button.className =
    "bg-blue-500 text-white font-bold py-2 px-4 rounded hover:bg-blue-600";
  button.innerText = "Search";
  container.appendChild(button);

  // Add event listener to update the state for the entered city
  button.addEventListener("click", () => {
    const city = input.value.trim();
    if (city) {
      updateState({ city });
    }
  });

  return container;
}

export default CitySelector;