// This service handles API calls to fetch weather data.
const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Ensure you set your API key in .env file
const BASE_URL = 'https://api.openweathermap.org/data/2.5/weather';

export const fetchWeatherData = async (city) => {
    try {
        const response = await fetch(`${BASE_URL}?q=${city}&appid=${API_KEY}&units=metric`);
        if (!response.ok) {
            throw new Error('City not found'); // Throw an error for non-200 responses
        }
        const data = await response.json();
        return data;
    } catch (error) {
        throw new Error(error.message); // Rethrow error for handling in the component
    }
};