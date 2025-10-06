import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import './WeatherDisplay.css';
import { fetchWeatherData } from '../services/weatherService';

/**
 * WeatherDisplay component fetches and displays the weather for a given city.
 * It handles errors related to API failures and invalid city names.
 * 
 * @param {Object} props - Component properties.
 * @param {string} props.city - The name of the city to fetch weather for.
 */
const WeatherDisplay = ({ city }) => {
  const [weather, setWeather] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!city) {
      setError('Please provide a valid city name.');
      return;
    }

    const fetchWeather = async () => {
      try {
        const data = await fetchWeatherData(city);
        setWeather(data);
        setError(''); // Clear any previous errors
      } catch (error) {
        setError('Failed to fetch weather data. Please try again later.');
        console.error("API fetch error:", error); // Log the error for debugging
      }
    };

    fetchWeather();
  }, [city]);

  return (
    <div className="weather-display">
      {error && <div className="error-message">{error}</div>}
      {weather && (
        <div className="weather-info">
          <h2>Weather in {weather.name}</h2>
          <p>Temperature: {weather.main.temp}°C</p>
          <p>Condition: {weather.weather[0].description}</p>
        </div>
      )}
    </div>
  );
};

WeatherDisplay.propTypes = {
  city: PropTypes.string.isRequired,
};

export default WeatherDisplay;