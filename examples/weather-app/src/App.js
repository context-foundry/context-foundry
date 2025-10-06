import React, { useEffect, useState } from 'react';
import WeatherCard from './components/WeatherCard';
import WeatherForecast from './components/WeatherForecast';
import './App.css';

const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Replace with your actual API key

/**
 * Main App component that fetches current weather and 5-day forecast from the API.
 * 
 * @returns {JSX.Element}
 */
const App = () => {
    const [currentWeather, setCurrentWeather] = useState(null);
    const [forecast, setForecast] = useState([]);

    useEffect(() => {
        const fetchWeatherData = async () => {
            try {
                const currentResponse = await fetch(`https://api.weather.com/current?apikey=${API_KEY}&location=YOUR_LOCATION`);
                const currentData = await currentResponse.json();
                setCurrentWeather(currentData);

                const forecastResponse = await fetch(`https://api.weather.com/forecast?apikey=${API_KEY}&location=YOUR_LOCATION`);
                const forecastData = await forecastResponse.json();
                setForecast(forecastData.daily);
            } catch (error) {
                console.error("Error fetching weather data:", error);
            }
        };

        fetchWeatherData();
    }, []);

    return (
        <div className="app">
            {currentWeather && (
                <WeatherCard
                    city={currentWeather.city}
                    temperature={currentWeather.temperature}
                    condition={currentWeather.condition}
                    icon={currentWeather.icon}
                />
            )}
            <WeatherForecast forecast={forecast} />
        </div>
    );
};

export default App;