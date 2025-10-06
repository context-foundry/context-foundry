import React from 'react';

/**
 * WeatherCard component to display weather information
 * @param {Object} props
 * @param {Object} props.weather The weather data
 * @param {string} props.error Error message, if any
 * @returns {JSX.Element}
 */
const WeatherCard = ({ weather, error }) => {
    return (
        <div className="weather-card">
            {error ? (
                <div className="error-message">{error}</div>
            ) : (
                <>
                    <h2>{weather.name}</h2>
                    <p>Temperature: {weather.main.temp} °C</p>
                    <p>Description: {weather.weather[0].description}</p>
                </>
            )}
        </div>
    );
};

export default WeatherCard;