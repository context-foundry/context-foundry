import React, { useState } from 'react';
import './Search.css';

/**
 * Search component for user input
 * @param {Object} props 
 * @param {function} props.onSearch - Callback function to handle search
 * @returns {JSX.Element} Rendered Search component
 */
const Search = ({ onSearch }) => {
  const [query, setQuery] = useState('');

  const handleSearch = (event) => {
    event.preventDefault();
    if (query) {
      onSearch(query);
      setQuery('');
    }
  };

  return (
    <form className="search-form" onSubmit={handleSearch}>
      <input
        type="text"
        placeholder="Enter city"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="search-input"
      />
      <button type="submit" className="search-button">Search</button>
    </form>
  );
};

export default Search;