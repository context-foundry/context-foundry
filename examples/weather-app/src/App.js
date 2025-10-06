import React, { useState, useEffect } from 'react';
import WeatherCard from './components/WeatherCard';
import 'bootstrap/dist/css/bootstrap.min.css';

/**
 * Main App component that fetches and displays weather data.
 * 
 * @returns {JSX.Element} The App component.
 */
const App = () => {
    const [weatherData, setWeatherData] = useState(null);

    useEffect(() => {
        const fetchWeather = async () => {
            const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Ensure you have your API key set in .env
            const response = await fetch(`https://api.weatherapi.com/v1/current.json?key=${API_KEY}&q=London`);
            const data = await response.json();
            setWeatherData(data);
        };

        fetchWeather();
    }, []);

    return (
        <div className="container mt-4">
            {weatherData ? (
                <WeatherCard
                    city={weatherData.location.name}
                    temperature={weatherData.current.temp_c}
                    condition={weatherData.current.condition.text}
                    icon={weatherData.current.condition.icon}
                />
            ) : (
                <p>Loading...</p>
            )}
        </div>
    );
};

export default App;