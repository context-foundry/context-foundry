import React, { createContext, useState, useContext } from 'react';

// Create a Context for the weather data
const WeatherContext = createContext();

// Create a Provider component
export const WeatherProvider = ({ children }) => {
  // State to hold the weather data
  const [weatherData, setWeatherData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Function to fetch weather data given a location
  const fetchWeatherData = async (location) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`API_URL_FOR_WEATHER_DATA?location=${location}`);
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      const data = await response.json();
      setWeatherData(data);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <WeatherContext.Provider value={{ weatherData, fetchWeatherData, loading, error }}>
      {children}
    </WeatherContext.Provider>
  );
};

// Custom hook to use the WeatherContext
export const useWeather = () => {
  const context = useContext(WeatherContext);
  if (!context) {
    throw new Error('useWeather must be used within a WeatherProvider');
  }
  return context;
};