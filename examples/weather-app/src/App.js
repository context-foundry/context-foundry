import React, { useState, useEffect } from 'react';
import './App.css';
import Weather from './Weather';
import Forecast from './components/Forecast';
import Search from './components/Search';
import { fetchWeatherData } from './api/weatherApi';

const App = () => {
    const [weatherData, setWeatherData] = useState(null);
    const [location, setLocation] = useState('');
    const [error, setError] = useState(null);

    // Fetch weather data when location changes
    useEffect(() => {
        if (location) {
            const fetchData = async () => {
                try {
                    const data = await fetchWeatherData(location);
                    setWeatherData(data);
                    setError(null); // Clear any previous errors
                } catch (err) {
                    setError('Unable to fetch weather data. Please try again.');
                    setWeatherData(null); // Clear any previous weather data
                }
            };

            fetchData();
        }
    }, [location]); // Only re-run if location changes

    const handleSearch = (searchTerm) => {
        setLocation(searchTerm); // Update location with user's search
    };

    return (
        <div className="App">
            <h1>Weather App</h1>
            <Search onSearch={handleSearch} />
            {error && <p className="error">{error}</p>}
            {weatherData && <Weather data={weatherData} />}
            {weatherData && <Forecast data={weatherData.forecast} />}
        </div>
    );
};

export default App;