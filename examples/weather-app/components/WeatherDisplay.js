import React from 'react';
import { useWeather } from '../App';

const WeatherDisplay = () => {
  const { weatherData } = useWeather();

  if (!weatherData) {
    return <p>No weather data available. Please enter a city.</p>;
  }

  return (
    <div>
      <h2>Weather in {weatherData.location.name}</h2>
      <p>Temperature: {weatherData.current.temp_c}°C</p>
      <p>Condition: {weatherData.current.condition.text}</p>
      <img src={weatherData.current.condition.icon} alt="weather icon" />
    </div>
  );
};

export default WeatherDisplay;