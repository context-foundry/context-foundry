import React from 'react';

function WeatherDisplay({ weatherData, errorMessage }) {
    return (
        <div className="weather-result">
            {errorMessage ? (
                <p className="error-message">{errorMessage}</p>
            ) : (
                <div className="weather-info">
                    <h2>{weatherData.location}</h2>
                    <p>{weatherData.temperature}°C</p>
                    <p>{weatherData.condition}</p>
                </div>
            )}
        </div>
    );
}

export default WeatherDisplay;