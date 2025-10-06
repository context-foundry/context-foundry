import React from 'react';

const LocationInput = ({ location, onLocationChange, onFetchWeather }) => {
    const handleChange = (event) => {
        onLocationChange(event.target.value);
    };

    const handleSubmit = (event) => {
        event.preventDefault();
        onFetchWeather();
    };

    return (
        <form onSubmit={handleSubmit}>
            <input
                type="text"
                value={location}
                onChange={handleChange}
                placeholder="Enter a location"
                required
            />
            <button type="submit">Get Weather</button>
        </form>
    );
};

export default LocationInput;