import React from 'react';
import { render } from '@testing-library/react';
import WeatherDisplay from './WeatherDisplay';

test('renders weather details when weather data is provided', () => {
  const weatherData = { temp: 20, condition: 'Sunny', humidity: 50 };
  const { getByText } = render(<WeatherDisplay city="New York" weather={weatherData} />);

  expect(getByText(/Weather in New York/i)).toBeInTheDocument();
  expect(getByText(/Temperature: 20 °C/i)).toBeInTheDocument();
  expect(getByText(/Condition: Sunny/i)).toBeInTheDocument();
  expect(getByText(/Humidity: 50%/i)).toBeInTheDocument();
});

test('does not render when no weather data is provided', () => {
  const { container } = render(<WeatherDisplay city="New York" weather={null} />);
  expect(container.firstChild).toBeNull();
});