import React, { useState } from 'react';

/**
 * A component for inputting a location to retrieve weather data.
 * @param {Function} onSubmit - The function to call when the form is submitted.
 * @returns {JSX.Element}
 */
const LocationInput = ({ onSubmit }) => {
  const [location, setLocation] = useState('');

  const handleInputChange = (e) => {
    setLocation(e.target.value);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (location) {
      onSubmit(location);
      setLocation('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex justify-center mb-4">
      <input 
        type="text" 
        value={location} 
        onChange={handleInputChange} 
        placeholder="Enter location" 
        className="border-2 border-gray-300 rounded-md p-2 w-full max-w-md"
      />
      <button 
        type="submit" 
        className="ml-2 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-700 transition"
      >
        Get Weather
      </button>
    </form>
  );
};

export default LocationInput;