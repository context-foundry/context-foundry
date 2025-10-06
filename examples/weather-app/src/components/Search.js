import React, { useState } from 'react';
import { fetchWeatherData } from '../api/weatherApi';
import WeatherCard from './WeatherCard';

/**
 * Search component for fetching weather data
 * @returns {JSX.Element}
 */
const Search = () => {
    const [city, setCity] = useState('');
    const [weather, setWeather] = useState(null);
    const [error, setError] = useState('');

    const handleSearch = async (e) => {
        e.preventDefault();
        setError('');  // Reset error message
        try {
            const data = await fetchWeatherData(city);
            setWeather(data);
        } catch (err) {
            setError(err.message);
            setWeather(null);
        }
    };

    return (
        <div>
            <form onSubmit={handleSearch}>
                <input
                    type="text"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="Enter city name"
                />
                <button type="submit">Get Weather</button>
            </form>
            {weather && <WeatherCard weather={weather} error={error} />}
            {error && <div className="error-message">{error}</div>}
        </div>
    );
};

export default Search;