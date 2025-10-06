import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherForecast from './WeatherForecast';

test('renders WeatherForecast with forecast items', () => {
    const forecast = [
        { date: 'Mon', temperature: 24 },
        { date: 'Tue', temperature: 22 },
        { date: 'Wed', temperature: 20 },
    ];

    render(<WeatherForecast forecast={forecast} />);
    
    forecast.forEach((day) => {
        expect(screen.getByText(day.date)).toBeInTheDocument();
        expect(screen.getByText(`${day.temperature}°C`)).toBeInTheDocument();
    });
});