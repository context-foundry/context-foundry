// Weather component to fetch and display weather information
import React, { useEffect, useState } from 'react';
import axios from 'axios';

const Weather = () => {
  const [weatherData, setWeatherData] = useState(null);
  const [loading, setLoading] = useState(true);
  const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Use your actual API key

  useEffect(() => {
    const fetchWeather = async () => {
      try {
        const response = await axios.get(`https://api.openweathermap.org/data/2.5/weather?q=London&appid=${API_KEY}`);
        setWeatherData(response.data);
      } catch (error) {
        console.error("Error fetching the weather data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchWeather();
  }, [API_KEY]);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!weatherData) {
    return <div>No data available</div>;
  }

  return (
    <div>
      <h2 className="text-2xl">{weatherData.name}</h2>
      <p>{weatherData.weather[0].description}</p>
      <p>Temperature: {Math.round(weatherData.main.temp - 273.15)} °C</p>
    </div>
  );
};

export default Weather;