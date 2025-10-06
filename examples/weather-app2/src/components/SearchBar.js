import React, { useState } from 'react';

/**
 * SearchBar component for user input.
 * 
 * @param {function} onSearch - Callback function to handle search submission.
 * @returns {JSX.Element}
 */
const SearchBar = ({ onSearch }) => {
    const [query, setQuery] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        onSearch(query);
        setQuery('');
    };

    return (
        <form onSubmit={handleSubmit} className="search-bar">
            <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter city name..."
                className="search-input"
            />
            <button type="submit" className="search-button">Search</button>
        </form>
    );
};

export default SearchBar;