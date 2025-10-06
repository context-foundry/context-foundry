import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherDisplay from '../components/WeatherDisplay';

describe('WeatherDisplay Component', () => {
  test('displays loading message when loading', () => {
    render(<WeatherDisplay loading={true} weatherData={null} error={null} />);
    expect(screen.getByText(/Loading.../i)).toBeInTheDocument();
  });

  test('displays error message when there is an error', () => {
    render(<WeatherDisplay loading={false} weatherData={null} error="Failed to fetch" />);
    expect(screen.getByText(/Error: Failed to fetch/i)).toBeInTheDocument();
  });

  test('displays weather information when data is available', () => {
    const weatherData = {
      location: 'New York',
      temperature: 25,
      condition: 'Sunny',
    };

    render(<WeatherDisplay loading={false} weatherData={weatherData} error={null} />);
    expect(screen.getByText(/Weather for New York/i)).toBeInTheDocument();
    expect(screen.getByText(/Temperature: 25°C/i)).toBeInTheDocument();
    expect(screen.getByText(/Condition: Sunny/i)).toBeInTheDocument();
  });
});