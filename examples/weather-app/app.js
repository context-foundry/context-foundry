document.getElementById('weather-form').addEventListener('submit', async function(event) {
    event.preventDefault();

    const city = document.getElementById('city-input').value;
    const weatherData = await fetchWeather(city);
    
    if (weatherData) {
        displayWeather(weatherData);
    }
});

/**
 * Display the weather data on the page.
 * @param {Object} data - The weather data object.
 */
function displayWeather(data) {
    const resultDiv = document.getElementById('weather-result');
    resultDiv.innerHTML = `
        <h2>${data.name}</h2>
        <p>Temperature: ${data.main.temp} °C</p>
        <p>Weather: ${data.weather[0].description}</p>
    `;
}