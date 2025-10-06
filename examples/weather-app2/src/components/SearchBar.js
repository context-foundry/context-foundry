import React, { useState } from 'react';

function SearchBar({ onSearch }) {
    const [location, setLocation] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (location.trim()) {
            onSearch(location);
            setLocation('');
        }
    };

    return (
        <form className="search-bar" onSubmit={handleSubmit}>
            <input
                type="text"
                className="border rounded w-full py-2 px-3 text-gray-700"
                placeholder="Enter location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
            />
            <button
                type="submit"
                className="mt-2 block w-full bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 rounded"
            >
                Search
            </button>
        </form>
    );
}

export default SearchBar;