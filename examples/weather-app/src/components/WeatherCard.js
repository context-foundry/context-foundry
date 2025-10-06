import React from 'react';

/**
 * WeatherCard component displays the weather information.
 * 
 * @param {Object} props - The properties passed to the component.
 * @param {string} props.city - The name of the city.
 * @param {number} props.temperature - The temperature in Celsius.
 * @param {string} props.condition - The current weather condition.
 */
const WeatherCard = ({ city, temperature, condition }) => {
    return (
        <div className="weather-card">
            <h2>{city}</h2>
            <p>{temperature}°C</p>
            <p>{condition}</p>
        </div>
    );
};

export default WeatherCard;