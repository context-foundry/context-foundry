import React from 'react';
import { render } from '@testing-library/react';
import WeatherCard from './WeatherCard';

describe('WeatherCard Component', () => {
  it('renders correctly with weather data', () => {
    const mockData = {
      name: 'New York',
      main: { temp: 24 },
      weather: [{ description: 'clear sky' }],
    };
    const { getByText } = render(<WeatherCard data={mockData} />);
    expect(getByText(/New York/i)).toBeInTheDocument();
    expect(getByText(/Temperature: 24 °C/i)).toBeInTheDocument();
    expect(getByText(/Weather: clear sky/i)).toBeInTheDocument();
  });
});