import React from 'react';
import WeatherCard from './WeatherCard';
import PropTypes from 'prop-types';
import './WeatherForecast.css';

/**
 * WeatherForecast component displays a 5-day weather forecast.
 * 
 * @param {Object} props - Component props
 * @param {Array} props.forecast - Array of forecast data for the next 5 days
 * @returns {JSX.Element}
 */
const WeatherForecast = ({ forecast }) => {
    return (
        <div className="weather-forecast">
            {forecast.map((day, index) => (
                <WeatherCard
                    key={index}
                    city={day.city}
                    temperature={day.temperature}
                    condition={day.condition}
                    icon={day.icon}
                />
            ))}
        </div>
    );
};

WeatherForecast.propTypes = {
    forecast: PropTypes.arrayOf(
        PropTypes.shape({
            city: PropTypes.string.isRequired,
            temperature: PropTypes.string.isRequired,
            condition: PropTypes.string.isRequired,
            icon: PropTypes.string.isRequired,
        })
    ).isRequired,
};

export default WeatherForecast;