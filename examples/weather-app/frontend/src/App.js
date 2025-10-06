import React, { useState, useEffect } from 'react';
import WeatherCard from './components/WeatherCard';
import WeatherForecast from './components/WeatherForecast';
import './App.css';

const API_KEY = process.env.REACT_APP_WEATHER_API_KEY;

const App = () => {
  const [weatherData, setWeatherData] = useState(null);
  const [location, setLocation] = useState('New York');

  useEffect(() => {
    const fetchWeather = async () => {
      try {
        const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${location}&appid=${API_KEY}&units=metric`);
        const data = await response.json();
        setWeatherData(data);
      } catch (error) {
        console.error('Error fetching the weather data:', error);
      }
    };

    fetchWeather();
  }, [location]);

  return (
    <div className="App">
      <h1>Weather App</h1>
      <input 
        type="text" 
        value={location} 
        onChange={(e) => setLocation(e.target.value)} 
        placeholder="Enter a city" 
      />
      {weatherData && (
        <>
          <WeatherCard data={weatherData} />
          <WeatherForecast location={location} />
        </>
      )}
    </div>
  );
};

export default App;