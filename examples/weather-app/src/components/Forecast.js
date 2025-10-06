import React from 'react';

/**
 * Forecast component displays a 5-day weather forecast.
 * 
 * @param {Array} forecast - Array of forecast objects containing date and temperature.
 */
const Forecast = ({ forecast }) => {
    return (
        <div className="forecast">
            <h3>5-Day Forecast</h3>
            <div className="forecast-cards">
                {forecast.map(({ date, temperature }, index) => (
                    <div key={index} className="forecast-card">
                        <p>{date}</p>
                        <p>{temperature}°C</p>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default Forecast;