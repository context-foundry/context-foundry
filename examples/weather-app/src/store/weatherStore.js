// Actual complete code for weather context and provider
import React, { createContext, useState, useEffect } from 'react';

// Create Weather Context
const WeatherContext = createContext();

// Weather Provider component
const WeatherProvider = ({ children }) => {
    const [weatherData, setWeatherData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Effect to fetch weather data
    const fetchWeatherData = async (location) => {
        setLoading(true);
        try {
            const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${location}&appid=${process.env.REACT_APP_WEATHER_API_KEY}&units=metric`);
            if (!response.ok) {
                throw new Error('Failed to fetch weather data');
            }
            const data = await response.json();
            setWeatherData(data);
            setError(null);
        } catch (err) {
            setError(err.message);
            setWeatherData(null);
        } finally {
            setLoading(false);
        }
    };

    return (
        <WeatherContext.Provider value={{ weatherData, loading, error, fetchWeatherData }}>
            {children}
        </WeatherContext.Provider>
    );
};

// Custom hook to use weather context
const useWeather = () => {
    const context = React.useContext(WeatherContext);
    if (!context) {
        throw new Error("useWeather must be used within a WeatherProvider");
    }
    return context;
};

export { WeatherProvider, useWeather };