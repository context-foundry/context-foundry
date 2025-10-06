import React, { useState } from 'react';
import PropTypes from 'prop-types';

/**
 * SearchBar Component.
 * A reusable input field to search for a city to fetch weather data.
 * 
 * Props:
 * - onSearch: Function - Callback to handle when a search is submitted.
 */
const SearchBar = ({ onSearch }) => {
  const [query, setQuery] = useState('');

  /**
   * Handles the submission of the search input
   * @param {React.FormEvent} e - The form submission event
   */
  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
      setQuery('');
    }
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        className="search-input"
        placeholder="Enter city name..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="City name"
      />
      <button type="submit" className="search-button" aria-label="Search">
        Search
      </button>
    </form>
  );
};

SearchBar.propTypes = {
  onSearch: PropTypes.func.isRequired,
};

export default SearchBar;