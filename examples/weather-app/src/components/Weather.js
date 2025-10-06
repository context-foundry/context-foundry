// Weather component to display the weather information

import React from 'react';
import { useSelector } from 'react-redux';

const Weather = () => {
    const { data, loading, error } = useSelector((state) => state.weather);

    if (loading) return <div>Loading...</div>;
    if (error) return <div>{error}</div>;

    return (
        <div>
            <h1>Weather in {data.location.name}</h1>
            <p>Temperature: {data.current.temp_c} °C</p>
            <p>Condition: {data.current.condition.text}</p>
        </div>
    );
};

export default Weather;