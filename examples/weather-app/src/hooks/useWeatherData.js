import { useState, useEffect } from 'react';

/**
 * Custom hook to fetch weather data based on the given city.
 * @param {string} city - The name of the city to fetch weather data for.
 * @returns {Object} - The weather data, error (if any), and loading state.
 */
const useWeatherData = (city) => {
  const [weatherData, setWeatherData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!city) {
      setWeatherData(null);
      setLoading(false);
      setError('City is required to fetch weather data.');
      return;
    }

    const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Load the API key from environment variables
    const API_URL = `https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}&units=metric`;

    setLoading(true);
    setError(null);

    async function fetchWeatherData() {
      try {
        const response = await fetch(API_URL);
        if (!response.ok) {
          throw new Error(`Error fetching weather data: ${response.statusText}`);
        }
        const data = await response.json();
        setWeatherData(data);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    }

    fetchWeatherData();
  }, [city]);

  return { weatherData, loading, error };
};

export default useWeatherData;