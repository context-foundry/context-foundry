import React from 'react';
import PropTypes from 'prop-types';

const Forecast = ({ data }) => {
    return (
        <div className="forecast">
            <h2>Forecast</h2>
            {data.map((day, index) => (
                <div key={index} className="forecast-card">
                    <p>Date: {day.date}</p>
                    <p>Max Temp: {day.day.maxtemp}°C</p>
                    <p>Min Temp: {day.day.mintemp}°C</p>
                    <p>Condition: {day.day.condition.text}</p>
                </div>
            ))}
        </div>
    );
};

Forecast.propTypes = {
    data: PropTypes.array.isRequired,
};

export default Forecast;