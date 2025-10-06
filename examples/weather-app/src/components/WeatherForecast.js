import React from 'react';
import './WeatherForecast.css';

/**
 * WeatherForecast component to display a forecast for the next few days.
 * 
 * @param {Object} props - Component properties
 * @param {Array} props.forecast - Array of forecast data
 * @returns {JSX.Element} Rendered WeatherForecast component
 */
const WeatherForecast = ({ forecast }) => {
    return (
        <div className="forecast-container">
            {forecast.map((day, index) => (
                <div key={index} className="forecast-item">
                    <h3>{day.date}</h3>
                    <div className="temp">{day.temperature}°C</div>
                </div>
            ))}
        </div>
    );
};

export default WeatherForecast;