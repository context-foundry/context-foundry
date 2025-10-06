import React, { useEffect, useState } from 'react';
import './WeatherForecast.css';

const WeatherForecast = ({ location }) => {
  const [forecastData, setForecastData] = useState([]);

  useEffect(() => {
    const fetchForecast = async () => {
      try {
        const response = await fetch(`https://api.openweathermap.org/data/2.5/forecast?q=${location}&appid=${API_KEY}&units=metric`);
        const data = await response.json();
        setForecastData(data.list);
      } catch (error) {
        console.error('Error fetching the weather forecast:', error);
      }
    };

    fetchForecast();
  }, [location]);

  return (
    <div className="weather-forecast">
      <h3>5-Day Forecast</h3>
      {forecastData.map((forecast, index) => (
        <div key={index} className="forecast-item">
          <p>{forecast.dt_txt}: {forecast.main.temp} °C, {forecast.weather[0].description}</p>
        </div>
      ))}
    </div>
  );
};

export default WeatherForecast;