import React from 'react';
import { render } from '@testing-library/react';
import WeatherCard from './WeatherCard';

describe('WeatherCard', () => {
    it('should display weather data', () => {
        const weather = {
            name: 'London',
            main: { temp: 15 },
            weather: [{ description: 'Clear' }]
        };
        const { getByText } = render(<WeatherCard weather={weather} error={null} />);
        
        expect(getByText(/London/i)).toBeInTheDocument();
        expect(getByText(/Temperature: 15 °C/i)).toBeInTheDocument();
        expect(getByText(/Description: Clear/i)).toBeInTheDocument();
    });

    it('should display error message', () => {
        const error = 'City not found';
        const { getByText } = render(<WeatherCard weather={null} error={error} />);
        
        expect(getByText(/City not found/i)).toBeInTheDocument();
    });
});