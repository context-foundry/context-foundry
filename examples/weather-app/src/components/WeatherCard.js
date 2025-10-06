import React from 'react';
import './WeatherCard.css';

/**
 * WeatherCard component to display individual weather information.
 * 
 * @param {Object} props - Component properties
 * @param {string} props.city - City name
 * @param {number} props.temperature - Temperature in Celsius
 * @param {string} props.condition - Weather condition (e.g., sunny, rainy)
 * @returns {JSX.Element} Rendered WeatherCard component
 */
const WeatherCard = ({ city, temperature, condition }) => {
    return (
        <div className="weather-card">
            <h2>{city}</h2>
            <div className="temperature">{temperature}°C</div>
            <div className="condition">{condition}</div>
        </div>
    );
};

export default WeatherCard;