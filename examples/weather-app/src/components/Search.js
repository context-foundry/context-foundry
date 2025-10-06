import React, { useState } from 'react';

/**
 * Search component for inputting location to get weather updates.
 * 
 * @param {function} onSearch - Function to call when searching for weather.
 */
const Search = ({ onSearch }) => {
    const [query, setQuery] = useState('');

    const handleSubmit = (event) => {
        event.preventDefault();
        if (query) {
            onSearch(query);
            setQuery('');
        }
    };

    return (
        <form onSubmit={handleSubmit}>
            <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter a city"
            />
            <button type="submit">Search</button>
        </form>
    );
};

export default Search;