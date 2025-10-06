import React from 'react';
import PropTypes from 'prop-types';

const Weather = ({ data }) => {
    return (
        <div className="weather">
            <h2>Current Weather</h2>
            <p>Location: {data.location.name}</p>
            <p>Temperature: {data.current.temp}°C</p>
            <p>Condition: {data.current.condition.text}</p>
        </div>
    );
};

Weather.propTypes = {
    data: PropTypes.object.isRequired,
};

export default Weather;