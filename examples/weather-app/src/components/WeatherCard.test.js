import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherCard from './WeatherCard';

test('renders WeatherCard with correct data', () => {
    const mockData = {
        location: 'New York',
        temperature: '22°C',
        description: 'Sunny',
    };

    render(<WeatherCard data={mockData} />);

    const locationElement = screen.getByText(/New York/i);
    const temperatureElement = screen.getByText(/Temperature: 22°C/i);
    const descriptionElement = screen.getByText(/Condition: Sunny/i);

    expect(locationElement).toBeInTheDocument();
    expect(temperatureElement).toBeInTheDocument();
    expect(descriptionElement).toBeInTheDocument();
});