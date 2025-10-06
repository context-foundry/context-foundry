import React from 'react';
import './Header.css';

/**
 * Header component for the Weather App
 * @returns {JSX.Element} Rendered Header component
 */
const Header = () => {
  return (
    <header className="header">
      <h1>Weather App</h1>
      <p>Get real-time weather updates</p>
    </header>
  );
};

export default Header;