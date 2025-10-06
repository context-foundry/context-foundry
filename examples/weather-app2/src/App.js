import React, { useState } from 'react';
import SearchBar from './components/SearchBar';
import WeatherDisplay from './components/WeatherDisplay';
import api from './services/api';

const App = () => {
    // State to store weather data and search input
    const [weatherData, setWeatherData] = useState(null);
    const [city, setCity] = useState('');

    // Function to handle the user's search
    const handleSearch = async (searchQuery) => {
        setCity(searchQuery);
        try {
            const data = await api.getWeatherData(searchQuery);
            setWeatherData(data);
        } catch (error) {
            console.error("Failed to fetch weather data:", error);
        }
    };

    return (
        <div className="app">
            <h1>Weather App</h1>
            <SearchBar onSearch={handleSearch} />
            {weatherData && <WeatherDisplay data={weatherData} />}
            {weatherData === null && <p>No data available. Please search for a city.</p>}
        </div>
    );
};

export default App;