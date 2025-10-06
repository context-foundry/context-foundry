// Frontend logic to fetch and display weather data
document.getElementById("weather-form").addEventListener("submit", async (event) => {
  event.preventDefault();

  const city = document.getElementById("city-input").value;

  try {
    const response = await fetch(`/api/weather/${city}`);
    if (!response.ok) {
      throw new Error("Failed to fetch weather data");
    }
    const data = await response.json();

    document.getElementById("weather-data").textContent = `
      City: ${data.name}
      Temperature: ${(data.main.temp - 273.15).toFixed(2)} °C
      Weather: ${data.weather[0].description}
    `;
  } catch (error) {
    document.getElementById("weather-data").textContent = error.message;
  }
});