import React from 'react';

const WeatherDisplay = ({ weatherData }) => {
    if (!weatherData) {
        return <p>No weather data available</p>;
    }

    const { main, weather, name } = weatherData;
    
    return (
        <div>
            <h2>Weather in {name}</h2>
            <p>Temperature: {main.temp} °C</p>
            <p>Condition: {weather[0].description}</p>
        </div>
    );
};

export default WeatherDisplay;