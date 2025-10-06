import React from 'react';
import PropTypes from 'prop-types';
import './WeatherDisplay.css';

/**
 * WeatherDisplay Component - Displays current weather conditions for a given city.
 *
 * @param {Object} props
 * @param {string} props.city - Name of the city for which weather data is displayed.
 * @param {Object} props.weatherData - Weather data object containing details like temperature, description, etc.
 * @returns {JSX.Element} React component rendering weather information.
 */
const WeatherDisplay = ({ city, weatherData }) => {
  if (!weatherData) {
    return (
      <div className="weather-display">
        <p className="weather-display__message">No weather data available. Please search for a city.</p>
      </div>
    );
  }

  const { temp, description, icon } = weatherData;

  return (
    <div className="weather-display">
      <h2 className="weather-display__title">Weather in {city}</h2>
      <div className="weather-display__content">
        <img
          className="weather-display__icon"
          src={`https://openweathermap.org/img/wn/${icon}@2x.png`}
          alt={description}
        />
        <p className="weather-display__temp">{Math.round(temp)}°C</p>
        <p className="weather-display__description">{description}</p>
      </div>
    </div>
  );
};

WeatherDisplay.propTypes = {
  city: PropTypes.string.isRequired,
  weatherData: PropTypes.shape({
    temp: PropTypes.number,
    description: PropTypes.string,
    icon: PropTypes.string,
  }),
};

WeatherDisplay.defaultProps = {
  weatherData: null,
};

export default WeatherDisplay;