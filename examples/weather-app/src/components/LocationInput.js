// Location input component to capture user's location input

import React, { useState } from 'react';
import { useDispatch } from 'react-redux';
import { fetchWeather } from '../actions/weatherActions';

const LocationInput = () => {
    const [location, setLocation] = useState('');
    const dispatch = useDispatch();

    const handleSubmit = (e) => {
        e.preventDefault();
        if (location) {
            dispatch(fetchWeather(location));
            setLocation('');
        }
    };

    return (
        <form onSubmit={handleSubmit}>
            <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Enter location"
                required
            />
            <button type="submit">Get Weather</button>
        </form>
    );
};

export default LocationInput;