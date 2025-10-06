// This component displays the weather information for the searched city
import React, { useState } from 'react';
import { fetchWeatherData } from '../services/api';

const WeatherDisplay = ({ city }) => {
    const [weather, setWeather] = useState(null);
    const [error, setError] = useState('');

    const handleFetchWeather = async () => {
        setError(''); // Clear previous error
        try {
            const data = await fetchWeatherData(city);
            setWeather(data);
        } catch (error) {
            setError(error.message); // Set error message for display
        }
    };

    // Fetch weather when city changes
    React.useEffect(() => {
        if (city) {
            handleFetchWeather();
        }
    }, [city]);

    return (
        <div>
            {error && <p style={{ color: 'red' }}>{error}</p>} {/* Display error message */}
            {weather && (
                <div>
                    <h1>{weather.name}</h1>
                    <p>{weather.main.temp} °C</p>
                    <p>{weather.weather[0].description}</p>
                </div>
            )}
        </div>
    );
};

export default WeatherDisplay;