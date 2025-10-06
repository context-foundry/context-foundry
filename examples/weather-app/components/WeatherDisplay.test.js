import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherDisplay from './WeatherDisplay';

test('renders WeatherDisplay component with weather data', () => {
    const mockWeatherData = {
        name: 'London',
        main: {
            temp: 15,
            humidity: 80,
        },
        weather: [{ description: 'clear sky' }],
    };

    render(<WeatherDisplay weatherData={mockWeatherData} />);

    expect(screen.getByText(/weather in london/i)).toBeInTheDocument();
    expect(screen.getByText(/temperature: 15°c/i)).toBeInTheDocument();
    expect(screen.getByText(/weather: clear sky/i)).toBeInTheDocument();
    expect(screen.getByText(/humidity: 80%/i)).toBeInTheDocument();
});

test('renders message when no weather data is provided', () => {
    render(<WeatherDisplay weatherData={null} />);
    expect(screen.getByText(/no weather data available/i)).toBeInTheDocument();
});