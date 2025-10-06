import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherDisplay from './WeatherDisplay';
import { WeatherContext } from '../App';

const mockWeatherData = {
  location: { name: 'London' },
  current: {
    temp_c: 15,
    condition: { text: 'Sunny', icon: 'https://some-icon-url.com/icon.png' }
  }
};

test('renders WeatherDisplay with weather data', () => {
  render(
    <WeatherContext.Provider value={{ weatherData: mockWeatherData }}>
      <WeatherDisplay />
    </WeatherContext.Provider>
  );

  expect(screen.getByText(/Weather in London/i)).toBeInTheDocument();
  expect(screen.getByText(/Temperature: 15°C/i)).toBeInTheDocument();
  expect(screen.getByText(/Condition: Sunny/i)).toBeInTheDocument();
  expect(screen.getByAltText(/weather icon/i)).toHaveAttribute('src', 'https://some-icon-url.com/icon.png');
});

test('renders message when no weather data is available', () => {
  render(
    <WeatherContext.Provider value={{ weatherData: null }}>
      <WeatherDisplay />
    </WeatherContext.Provider>
  );

  expect(screen.getByText(/No weather data available/i)).toBeInTheDocument();
});