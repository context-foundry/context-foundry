import React, { useState } from 'react';
import CitySearch from './components/CitySearch';
import WeatherDisplay from './components/WeatherDisplay';
import './style.css';

const App = () => {
    const [city, setCity] = useState('');
    const [weatherData, setWeatherData] = useState(null);

    const handleCityChange = (newCity) => {
        setCity(newCity);
    };

    const handleFetchWeather = async () => {
        // Fetch weather data logic here (API call)
        // For demonstration, we will use a mock response
        const mockWeatherData = {
            city: city,
            temperature: 23,
            condition: 'Sunny',
            description: 'Clear Sky',
        };
        setWeatherData(mockWeatherData);
    };

    return (
        <div className="header">
            <h1 className="text-2xl font-bold">Weather App</h1>
            <div className="city-search">
                <CitySearch onCityChange={handleCityChange} />
                <button className="button" onClick={handleFetchWeather}>Get Weather</button>
            </div>
            {weatherData && <WeatherDisplay data={weatherData} />}
            <footer className="footer">© 2023 Weather App</footer>
        </div>
    );
};

export default App;