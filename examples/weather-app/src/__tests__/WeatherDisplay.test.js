import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherDisplay from '../components/WeatherDisplay';

describe('WeatherDisplay Component', () => {
  test('renders weather data correctly', () => {
    const weatherData = {
      name: 'New York',
      main: {
        temp: 23,
      },
      weather: [
        {
          description: 'Clear sky',
        },
      ],
    };

    render(<WeatherDisplay weatherData={weatherData} />);

    expect(screen.getByText(/new york/i)).toBeInTheDocument();
    expect(screen.getByText(/temperature: 23 °c/i)).toBeInTheDocument();
    expect(screen.getByText(/condition: clear sky/i)).toBeInTheDocument();
  });

  test('returns null when no weather data is provided', () => {
    const { container } = render(<WeatherDisplay weatherData={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});