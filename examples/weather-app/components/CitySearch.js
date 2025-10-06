import React from 'react';
import { useWeather } from '../App';

const CitySearch = () => {
  const { city, setCity, fetchWeather } = useWeather();

  const handleSubmit = (e) => {
    e.preventDefault();
    fetchWeather(city);
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={city}
        onChange={(e) => setCity(e.target.value)}
        placeholder="Enter city"
      />
      <button type="submit">Get Weather</button>
    </form>
  );
};

export default CitySearch;