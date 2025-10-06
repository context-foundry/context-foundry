import React from 'react';

const Weather = ({ data }) => {
  const { main, weather } = data;

  return (
    <div>
      <h2>{data.name}</h2>
      <p>Temperature: {(main.temp - 273.15).toFixed(2)}°C</p>
      <p>Weather: {weather[0].description}</p>
    </div>
  );
};

export default Weather;