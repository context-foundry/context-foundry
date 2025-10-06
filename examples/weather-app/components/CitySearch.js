import React, { useState } from 'react';

/**
 * CitySearch component to handle user input for city search.
 * @param {object} props - Props for the component.
 * @param {function} props.onSearch - Callback function to handle the search action.
 * @returns {JSX.Element} The rendered component.
 */
const CitySearch = ({ onSearch }) => {
    const [city, setCity] = useState('');

    const handleInputChange = (event) => {
        setCity(event.target.value);
    };

    const handleSearch = (event) => {
        event.preventDefault();
        onSearch(city);
        setCity('');
    };

    return (
        <form onSubmit={handleSearch}>
            <input 
                type="text" 
                value={city} 
                onChange={handleInputChange} 
                placeholder="Enter city name" 
                required 
            />
            <button type="submit">Search</button>
        </form>
    );
};

export default CitySearch;