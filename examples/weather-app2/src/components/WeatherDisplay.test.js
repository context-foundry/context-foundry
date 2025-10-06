import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherDisplay from './WeatherDisplay';

test('displays weather data correctly', () => {
    const weatherData = {
        city: 'New York',
        temperature: 25,
        conditions: 'Sunny',
    };

    render(<WeatherDisplay weatherData={weatherData} />);

    expect(screen.getByText(/New York/i)).toBeInTheDocument();
    expect(screen.getByText(/Temperature: 25 °C/i)).toBeInTheDocument();
    expect(screen.getByText(/Conditions: Sunny/i)).toBeInTheDocument();
});

test('displays no data message when no weather data is provided', () => {
    render(<WeatherDisplay weatherData={null} />);

    expect(screen.getByText(/no data available/i)).toBeInTheDocument();
});