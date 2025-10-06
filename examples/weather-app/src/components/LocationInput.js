import React, { useState } from 'react';

/**
 * LocationInput component for user input of location.
 * @param {Object} props - Component props.
 * @param {function} props.onSubmit - Function to handle the location submission.
 * @returns {JSX.Element} Rendered component.
 */
const LocationInput = ({ onSubmit }) => {
  const [location, setLocation] = useState('');

  const handleChange = (event) => {
    setLocation(event.target.value);
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    if (location) {
      onSubmit(location);
      setLocation('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center">
      <input
        type="text"
        value={location}
        onChange={handleChange}
        placeholder="Enter location"
        className="border border-gray-300 rounded p-2"
      />
      <button type="submit" className="ml-2 bg-blue-500 text-white rounded p-2">
        Get Weather
      </button>
    </form>
  );
};

export default LocationInput;