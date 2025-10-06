import React, { useContext } from 'react';
import WeatherCard from './WeatherCard'; // Import WeatherCard for individual day representation
import { WeatherContext } from '../context/WeatherContext';

/**
 * Forecast Component
 * Renders a 5-day weather forecast using data from WeatherContext.
 */
const Forecast = () => {
  const { forecastData } = useContext(WeatherContext); // Fetch forecast data from WeatherContext

  if (!forecastData || forecastData.length === 0) {
    return (
      <div className="text-center text-gray-600">
        <p>No forecast data available.</p>
      </div>
    );
  }

  return (
    <div className="py-6 px-4">
      <h2 className="text-xl font-semibold text-center mb-4">5-Day Weather Forecast</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {forecastData.map((day, index) => (
          <WeatherCard
            key={index}
            date={day.date}
            temperature={day.temperature}
            description={day.description}
            icon={day.icon}
          />
        ))}
      </div>
    </div>
  );
};

export default Forecast;