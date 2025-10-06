import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherCard from './WeatherCard';

test('renders WeatherCard with city name, temperature, and condition', () => {
    render(<WeatherCard city="New York" temperature={25} condition="Sunny" />);
    expect(screen.getByText(/new york/i)).toBeInTheDocument();
    expect(screen.getByText(/25/i)).toBeInTheDocument();
    expect(screen.getByText(/sunny/i)).toBeInTheDocument();
});