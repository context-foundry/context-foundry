import React from 'react';

/**
 * A component for displaying the weather information.
 * @param {Object} weather - The weather data to display.
 * @returns {JSX.Element}
 */
const WeatherDisplay = ({ weather }) => {
  if (!weather) {
    return <p className="text-center">Please enter a location to see the weather.</p>;
  }

  return (
    <div className="max-w-md mx-auto bg-white shadow-md rounded-lg p-4">
      <h2 className="text-xl font-bold text-center">{weather.location}</h2>
      <p className="text-center">{weather.description}</p>
      <p className="text-2xl font-bold text-center">{weather.temperature}°C</p>
      <p className="text-center text-gray-600">{weather.humidity}% Humidity</p>
    </div>
  );
};

export default WeatherDisplay;