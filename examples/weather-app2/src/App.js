import React, { useState } from 'react';
import SearchBar from './components/SearchBar';
import WeatherDisplay from './components/WeatherDisplay';
import './index.css';

function App() {
    const [weatherData, setWeatherData] = useState(null);
    const [errorMessage, setErrorMessage] = useState('');

    const fetchWeatherData = async (location) => {
        const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Use real API key
        const response = await fetch(`https://api.weatherapi.com/v1/current.json?key=${API_KEY}&q=${location}`);
        
        if (!response.ok) {
            setErrorMessage('Failed to fetch weather data. Please try again.');
            return;
        }

        const data = await response.json();
        setWeatherData({
            location: data.location.name,
            temperature: data.current.temp_c,
            condition: data.current.condition.text
        });
        setErrorMessage('');
    };

    return (
        <div className="container">
            <h1>Weather App</h1>
            <SearchBar onSearch={fetchWeatherData} />
            <WeatherDisplay weatherData={weatherData} errorMessage={errorMessage} />
        </div>
    );
}

export default App;