/**
 * Fetch the weather data for a given city.
 * @param {string} city - The name of the city to fetch weather for.
 * @returns {Promise<Object|null>} - Returns weather data or null if error occurs.
 */
async function fetchWeather(city) {
    const apiKey = 'YOUR_API_KEY'; // Replace with your actual API Key
    const url = `https://api.openweathermap.org/data/2.5/weather?q=${city}&units=metric&appid=${apiKey}`;
    
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('City not found');
        return await response.json();
    } catch (error) {
        console.error('Error fetching the weather data:', error);
        return null;
    }
}