import React, { useState } from 'react';
import PropTypes from 'prop-types';

const Search = ({ onSearch }) => {
    const [inputValue, setInputValue] = useState('');

    const handleInputChange = (event) => {
        setInputValue(event.target.value);
    };

    const handleSubmit = (event) => {
        event.preventDefault();
        onSearch(inputValue); // Pass the search term to the parent component
        setInputValue(''); // Clear input after search
    };

    return (
        <form onSubmit={handleSubmit}>
            <input
                type="text"
                placeholder="Enter location"
                value={inputValue}
                onChange={handleInputChange}
                required
            />
            <button type="submit">Search</button>
        </form>
    );
};

Search.propTypes = {
    onSearch: PropTypes.func.isRequired,
};

export default Search;