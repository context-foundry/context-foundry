import React, { useState } from 'react';

const SearchBar = ({ onSearch }) => {
    const [inputValue, setInputValue] = useState('');

    const handleChange = (event) => {
        setInputValue(event.target.value);
    };

    const handleSubmit = (event) => {
        event.preventDefault();
        onSearch(inputValue);
        setInputValue(''); // Clear input after search
    };

    return (
        <form onSubmit={handleSubmit}>
            <input 
                type="text" 
                value={inputValue} 
                onChange={handleChange} 
                placeholder="Enter city name" 
                required 
            />
            <button type="submit">Search</button>
        </form>
    );
};

export default SearchBar;