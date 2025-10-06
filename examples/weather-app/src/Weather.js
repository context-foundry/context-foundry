import React, { useEffect, useState } from 'react';
import Forecast from './components/Forecast';
import Search from './components/Search';
import WeatherCard from './components/WeatherCard';
import './App.css';

const Weather = () => {
    const [weatherData, setWeatherData] = useState(null);
    const [forecasts, setForecasts] = useState([]);
    const [city, setCity] = useState('');

    const API_KEY = process.env.REACT_APP_API_KEY;

    const fetchWeather = async (city) => {
        const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}&units=metric`);
        const data = await response.json();
        return data;
    };

    const fetchForecast = async (city) => {
        const response = await fetch(`https://api.openweathermap.org/data/2.5/forecast?q=${city}&appid=${API_KEY}&units=metric`);
        const data = await response.json();
        return data.list;
    };

    const handleSearch = async (query) => {
        const weatherData = await fetchWeather(query);
        setWeatherData({
            city: weatherData.name,
            temperature: weatherData.main.temp,
            weather: weatherData.weather[0].description,
        });

        const forecastData = await fetchForecast(query);
        const forecastList = forecastData.slice(0, 5).map(item => ({
            date: new Date(item.dt * 1000).toLocaleDateString(),
            weather: item.weather[0].description,
            temperature: item.main.temp,
        }));
        setForecasts(forecastList);
        setCity(query);
    };

    return (
        <div className="container">
            <h1>Weather App</h1>
            <Search onSearch={handleSearch} />
            {weatherData && <WeatherCard {...weatherData} />}
            <Forecast forecasts={forecasts} />
        </div>
    );
};

export default Weather;