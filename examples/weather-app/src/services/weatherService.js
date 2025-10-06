const API_KEY = 'your_api_key_here'; // Replace with your actual API Key
const BASE_URL = 'https://api.openweathermap.org/data/2.5/weather';

export const fetchWeatherData = async ({ latitude, longitude } = {}) => {
    let url = BASE_URL;

    if (latitude && longitude) {
        url += `?lat=${latitude}&lon=${longitude}&appid=${API_KEY}&units=metric`;
    } else {
        url += `?q=${latitude}&appid=${API_KEY}&units=metric`;
    }

    const response = await fetch(url);
    if (!response.ok) {
        throw new Error('Failed to fetch weather data');
    }
    return response.json();
};