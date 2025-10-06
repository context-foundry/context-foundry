import React, { createContext, useContext, useState } from 'react';
import CitySearch from './components/CitySearch';
import WeatherDisplay from './components/WeatherDisplay';
import './App.css';

// Create a Context for the Weather Data
const WeatherContext = createContext();

function App() {
  const [weatherData, setWeatherData] = useState(null);
  const [city, setCity] = useState('');

  const fetchWeather = async (city) => {
    const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Ensure your API key is set in environment variables
    const response = await fetch(`https://api.weatherapi.com/v1/current.json?key=${API_KEY}&q=${city}`);
    const data = await response.json();
    setWeatherData(data);
  };

  return (
    <WeatherContext.Provider value={{ weatherData, fetchWeather, city, setCity }}>
      <div className="App">
        <h1>Weather App</h1>
        <CitySearch />
        <WeatherDisplay />
      </div>
    </WeatherContext.Provider>
  );
}

// Custom hook to use weather context
export const useWeather = () => {
  return useContext(WeatherContext);
};

export default App;