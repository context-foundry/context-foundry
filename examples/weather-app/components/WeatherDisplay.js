import React from 'react';

const WeatherDisplay = ({ data }) => {
    return (
        <div className="weather-display">
            <h2 className="text-xl font-semibold">{data.city}</h2>
            <div className="weather-info">
                <p className="text-lg">{data.temperature}°C</p>
                <p className="text-sm">{data.condition} - {data.description}</p>
            </div>
        </div>
    );
};

export default WeatherDisplay;