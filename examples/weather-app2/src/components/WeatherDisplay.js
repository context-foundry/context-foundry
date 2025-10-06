import React from 'react';

/**
 * WeatherDisplay component to show weather data.
 * 
 * @param {Object} weatherData - The weather data to display.
 * @returns {JSX.Element}
 */
const WeatherDisplay = ({ weatherData }) => {
    if (!weatherData) {
        return <div className="weather-display">No data available.</div>;
    }

    return (
        <div className="weather-display">
            <h2>{weatherData.city}</h2>
            <p>Temperature: {weatherData.temperature} °C</p>
            <p>Conditions: {weatherData.conditions}</p>
        </div>
    );
};

export default WeatherDisplay;