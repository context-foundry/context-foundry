// Optimized main application code (React)
import React from 'react';
import SearchBar from './components/SearchBar';
import WeatherDisplay from './components/WeatherDisplay';
import './styles/index.css';

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Weather App</h1>
      </header>
      <SearchBar />
      <WeatherDisplay />
    </div>
  );
}

export default App;