import React, { useState, useEffect } from 'react';
import Weather from './Weather';

const App = () => {
  const [weatherData, setWeatherData] = useState(null);
  const [city, setCity] = useState('New York');
  const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Replace with your real API key

  useEffect(() => {
    fetchWeather();
  }, [city]);

  const fetchWeather = async () => {
    const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}`);
    const data = await response.json();
    setWeatherData(data);
  };

  return (
    <div>
      <h1>Weather App</h1>
      <input 
        type="text" 
        value={city} 
        onChange={(e) => setCity(e.target.value)} 
        placeholder="Enter city name" 
      />
      {weatherData && <Weather data={weatherData} />}
    </div>
  );
}

export default App;