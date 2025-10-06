import React from 'react';
import axios from 'axios';
import './App.css';

const App = () => {
  const [weatherData, setWeatherData] = React.useState(null);
  const [location, setLocation] = React.useState('');

  const fetchWeather = () => {
    const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Use your actual API key
    axios.get(`https://api.openweathermap.org/data/2.5/weather?q=${location}&appid=${API_KEY}`)
      .then(response => {
        setWeatherData(response.data);
      })
      .catch(error => {
        console.error("There was an error fetching the weather data!", error);
      });
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    fetchWeather();
  };

  return (
    <div className="app">
      <h1>Weather App</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Enter location"
          required
        />
        <button type="submit">Get Weather</button>
      </form>
      {weatherData && (
        <div className="weather-info">
          <h2>{weatherData.name}</h2>
          <p>{Math.round(weatherData.main.temp - 273.15)} °C</p>
          <p>{weatherData.weather[0].description}</p>
        </div>
      )}
    </div>
  );
};

export default App;