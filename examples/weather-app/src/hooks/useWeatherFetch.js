import { useState, useEffect } from 'react';

/**
 * Custom hook for fetching weather data from OpenWeatherMap API.
 * 
 * @param {string} city - The name of the city to fetch weather data for.
 * @returns {object} - An object containing the weather data, loading state, and error message.
 */
const useWeatherFetch = (city) => {
    const [weatherData, setWeatherData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Ensure to set this in your .env file

    useEffect(() => {
        const fetchWeather = async () => {
            setLoading(true);
            setError(null);
            try {
                const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}&units=metric`);
                if (!response.ok) {
                    throw new Error('Failed to fetch weather data');
                }
                const data = await response.json();
                setWeatherData(data);
            } catch (error) {
                setError(error.message);
            } finally {
                setLoading(false);
            }
        };

        if (city) {
            fetchWeather();
        }
    }, [city, API_KEY]);

    return { weatherData, loading, error };
};

export default useWeatherFetch;