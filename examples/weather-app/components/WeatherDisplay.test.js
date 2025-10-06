import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherDisplay from './WeatherDisplay';

test('renders weather data correctly', () => {
    const weatherData = {
        city: "New York",
        temperature: 25,
        condition: "Sunny",
        description: "Clear Sky"
    };
    
    render(<WeatherDisplay data={weatherData} />);
    
    const cityElement = screen.getByText(/new york/i);
    const temperatureElement = screen.getByText(/25°c/i);
    const conditionElement = screen.getByText(/sunny - clear sky/i);

    expect(cityElement).toBeInTheDocument();
    expect(temperatureElement).toBeInTheDocument();
    expect(conditionElement).toBeInTheDocument();
});