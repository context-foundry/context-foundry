// JavaScript file to fetch weather data and display it on the front end
document.addEventListener('DOMContentLoaded', () => {
    const weatherDataElement = document.getElementById('weather-data');

    fetch('http://127.0.0.1:5000/weather')
        .then(response => response.json())
        .then(data => {
            const { city, temperature, condition } = data;
            weatherDataElement.textContent = `City: ${city}, Temperature: ${temperature}, Condition: ${condition}`;
        })
        .catch(error => {
            weatherDataElement.textContent = 'Failed to fetch weather data.';
            console.error('Error:', error);
        });
});