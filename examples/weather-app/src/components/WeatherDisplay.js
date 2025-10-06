import React from 'react';

/**
 * WeatherDisplay component to show weather data.
 * 
 * @param {Object} props - Weather data to display.
 * @param {string} props.city - City name.
 * @param {number} props.temperature - Temperature in Celsius.
 * @param {string} props.description - Weather description.
 */
const WeatherDisplay = ({ city, temperature, description }) => {
    return (
        <div className="weather-display">
            {city && (
                <h2 className="city-name">{city}</h2>
            )}
            {temperature !== undefined && (
                <p className="temperature">Temperature: {temperature}°C</p>
            )}
            {description && (
                <p className="description">Description: {description}</p>
            )}
        </div>
    );
};

export default WeatherDisplay;