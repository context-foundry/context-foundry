import React, { useEffect } from 'react';
import { useStore } from './store/weatherStore';
import Header from './components/Header';
import Search from './components/Search';
import WeatherDisplay from './components/WeatherDisplay';

const App = () => {
  const { fetchWeather, weatherData, error } = useStore();

  const handleSearch = (location) => {
    fetchWeather(location);
  };

  useEffect(() => {
    // Fetch weather data for a default location on initial load
    fetchWeather('New York');
  }, [fetchWeather]);

  return (
    <div className="App">
      <Header />
      <Search onSearch={handleSearch} />
      {error && <p className="error">{error}</p>}
      <WeatherDisplay data={weatherData} />
    </div>
  );
};

export default App;