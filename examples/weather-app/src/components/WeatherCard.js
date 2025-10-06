import React from 'react';
import PropTypes from 'prop-types';
import './WeatherCard.css';

/**
 * WeatherCard component displays the current weather for a specific location.
 * 
 * @param {Object} props - Component props
 * @param {string} props.city - The name of the city
 * @param {string} props.temperature - The current temperature
 * @param {string} props.condition - The current weather condition
 * @param {string} props.icon - Weather icon URL
 * @returns {JSX.Element}
 */
const WeatherCard = ({ city, temperature, condition, icon }) => {
    return (
        <div className="weather-card">
            <h2>{city}</h2>
            <img src={icon} alt={condition} />
            <p>{temperature}°C</p>
            <p>{condition}</p>
        </div>
    );
};

WeatherCard.propTypes = {
    city: PropTypes.string.isRequired,
    temperature: PropTypes.string.isRequired,
    condition: PropTypes.string.isRequired,
    icon: PropTypes.string.isRequired,
};

export default WeatherCard;