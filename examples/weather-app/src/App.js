// Main application component
import React from 'react';
import Weather from './components/Weather';

const App = () => {
  return (
    <div className="bg-gray-100 min-h-screen flex flex-col items-center justify-center">
      <h1 className="text-4xl font-bold mb-4">Weather App</h1>
      <Weather />
    </div>
  );
};

export default App;