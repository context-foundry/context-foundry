import React from 'react';

/**
 * WeatherDisplay component renders the weather information along with loading and error states.
 * 
 * @param {Object} props - The component props
 * @param {Object} props.weatherData - The weather data to display
 * @param {boolean} props.loading - Indicates if the data is loading
 * @param {string|null} props.error - Error message if there is an error
 */
const WeatherDisplay = ({ weatherData, loading, error }) => {
  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  if (error) {
    return <div className="error">Error: {error}</div>;
  }

  return (
    <div className="weather-display">
      <h1>Weather for {weatherData.location}</h1>
      <p>Temperature: {weatherData.temperature}°C</p>
      <p>Condition: {weatherData.condition}</p>
    </div>
  );
};

export default WeatherDisplay;