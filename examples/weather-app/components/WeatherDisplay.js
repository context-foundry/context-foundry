import React from 'react';

/**
 * WeatherDisplay component to show weather data.
 * @param {object} props - Props for the component.
 * @param {object} props.weatherData - Weather data to display.
 * @returns {JSX.Element} The rendered component.
 */
const WeatherDisplay = ({ weatherData }) => {
    if (!weatherData) {
        return <div>No weather data available.</div>;
    }

    return (
        <div>
            <h2>Weather in {weatherData.name}</h2>
            <p>Temperature: {weatherData.main.temp}°C</p>
            <p>Weather: {weatherData.weather[0].description}</p>
            <p>Humidity: {weatherData.main.humidity}%</p>
        </div>
    );
};

export default WeatherDisplay;