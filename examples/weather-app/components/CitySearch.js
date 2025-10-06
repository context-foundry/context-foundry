import React from 'react';

const CitySearch = ({ onCityChange }) => {
    const handleChange = (event) => {
        onCityChange(event.target.value);
    };

    return (
        <input
            type="text"
            className="input"
            placeholder="Enter city"
            onChange={handleChange}
        />
    );
};

export default CitySearch;