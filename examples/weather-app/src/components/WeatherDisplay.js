import React from 'react';

/**
 * WeatherDisplay component to showcase weather data.
 * @param {Object} props - Component props.
 * @param {Object} props.weatherData - Weather data object to display.
 * @returns {JSX.Element} Rendered component.
 */
const WeatherDisplay = ({ weatherData }) => {
  if (!weatherData) {
    return null;
  }

  const { name, main, weather } = weatherData;
  return (
    <div className="weather-display border border-gray-300 rounded p-4">
      <h2 className="text-xl font-bold">{name}</h2>
      <p className="text-lg">Temperature: {main.temp} °C</p>
      <p className="text-lg">Condition: {weather[0].description}</p>
    </div>
  );
};

export default WeatherDisplay;