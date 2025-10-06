import React from "react";
import PropTypes from "prop-types";
import "../styles/index.css"; // Importing shared styles

/**
 * ForecastCard component for displaying individual forecast data
 * @param {Object} props - The props object
 * @param {string} props.day - The day of the week (e.g., "Monday")
 * @param {string} props.date - The date in "YYYY-MM-DD" format
 * @param {number} props.temperature - The temperature in degrees Celsius
 * @param {string} props.weatherDescription - Short description of the weather (e.g., "Cloudy")
 * @param {string} props.icon - Weather icon URL
 * @returns {JSX.Element} The ForecastCard component
 */
const ForecastCard = ({ day, date, temperature, weatherDescription, icon }) => {
  return (
    <div className="forecast-card">
      <h3 className="forecast-card-day">{day}</h3>
      <p className="forecast-card-date">{date}</p>
      <img className="forecast-card-icon" src={icon} alt={weatherDescription} />
      <p className="forecast-card-temperature">{temperature}°C</p>
      <p className="forecast-card-description">{weatherDescription}</p>
    </div>
  );
};

// Define PropTypes for validation
ForecastCard.propTypes = {
  day: PropTypes.string.isRequired,
  date: PropTypes.string.isRequired,
  temperature: PropTypes.number.isRequired,
  weatherDescription: PropTypes.string.isRequired,
  icon: PropTypes.string.isRequired,
};

export default ForecastCard;