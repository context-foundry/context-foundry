import React from 'react';
import PropTypes from 'prop-types';

const WeatherCard = ({ data }) => {
    return (
        <div className="card">
            <div className="card-body">
                <h5 className="card-title">{data.location}</h5>
                <p className="card-text">Temperature: {data.temperature}</p>
                <p className="card-text">Condition: {data.description}</p>
            </div>
        </div>
    );
};

WeatherCard.propTypes = {
    data: PropTypes.shape({
        location: PropTypes.string.isRequired,
        temperature: PropTypes.string.isRequired,
        description: PropTypes.string.isRequired,
    }).isRequired,
};

export default WeatherCard;