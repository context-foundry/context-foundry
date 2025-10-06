import { useState, useEffect } from 'react';

/**
 * Custom hook for fetching weather data.
 * 
 * @param {string} location - The location to fetch weather data for
 * @returns {Object} - An object containing weather data, loading state, and error message
 */
const useWeatherFetch = (location) => {
  const [weatherData, setWeatherData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchWeather = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`https://api.example.com/weather?location=${location}`);
        if (!response.ok) {
          throw new Error('Failed to fetch weather data');
        }

        const data = await response.json();
        setWeatherData(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (location) {
      fetchWeather();
    }
  }, [location]);

  return { weatherData, loading, error };
};

export default useWeatherFetch;