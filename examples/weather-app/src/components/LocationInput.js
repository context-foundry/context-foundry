import React, { useState } from 'react';

/**
 * LocationInput component to capture user input for location.
 * 
 * @param {function} onSubmit - Callback function to handle the location input submission.
 */
const LocationInput = ({ onSubmit }) => {
    const [location, setLocation] = useState('');

    const handleInputChange = (event) => {
        setLocation(event.target.value);
    };

    const handleFormSubmit = (event) => {
        event.preventDefault();
        onSubmit(location);
        setLocation(''); // Clear input after submission
    };

    return (
        <form onSubmit={handleFormSubmit} className="location-input">
            <input 
                type="text" 
                value={location} 
                onChange={handleInputChange} 
                placeholder="Enter location" 
                required 
                className="input-field"
            />
            <button type="submit" className="submit-button">Get Weather</button>
        </form>
    );
};

export default LocationInput;