import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherDisplay from '../components/WeatherDisplay';

describe('WeatherDisplay component', () => {
  it('renders a message when no weather data is available', () => {
    render(<WeatherDisplay city="New York" />);
    const message = screen.getByText(/No weather data available. Please search for a city./i);
    expect(message).toBeInTheDocument();
  });

  it('renders weather information when data is provided', () => {
    const mockWeatherData = {
      temp: 25,
      description: 'Clear sky',
      icon: '01d',
    };
    render(<WeatherDisplay city="New York" weatherData={mockWeatherData} />);

    const title = screen.getByText(/Weather in New York/i);
    expect(title).toBeInTheDocument();

    const temp = screen.getByText(/25°C/i);
    expect(temp).toBeInTheDocument();

    const description = screen.getByText(/Clear sky/i);
    expect(description).toBeInTheDocument();

    const icon = screen.getByAltText(/Clear sky/i);
    expect(icon).toBeInTheDocument();
  });

  it('matches the snapshot', () => {
    const mockWeatherData = {
      temp: 15,
      description: 'Cloudy',
      icon: '03d',
    };
    const { asFragment } = render(<WeatherDisplay city="Los Angeles" weatherData={mockWeatherData} />);
    expect(asFragment()).toMatchSnapshot();
  });
});