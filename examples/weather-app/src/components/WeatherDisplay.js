import React from 'react';
import './WeatherDisplay.css';

/**
 * WeatherDisplay component to show weather details
 * @param {Object} props 
 * @param {string} props.city - Name of the city
 * @param {Object} props.weather - Weather data object
 * @returns {JSX.Element} Rendered WeatherDisplay component
 */
const WeatherDisplay = ({ city, weather }) => {
  if (!weather) {
    return null;
  }

  return (
    <div className="weather-display">
      <h2>Weather in {city}</h2>
      <p>Temperature: {weather.temp} °C</p>
      <p>Condition: {weather.condition}</p>
      <p>Humidity: {weather.humidity}%</p>
    </div>
  );
};

export default WeatherDisplay;