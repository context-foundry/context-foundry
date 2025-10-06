import React from 'react';
import { render } from '@testing-library/react';
import WeatherDisplay from '../WeatherDisplay';

describe('WeatherDisplay Component', () => {
    it('should display weather data when provided', () => {
        const weatherData = {
            main: { temp: 20 },
            weather: [{ description: 'clear sky' }],
            name: 'New York'
        };
        const { getByText } = render(<WeatherDisplay weatherData={weatherData} />);
        
        expect(getByText(/Weather in New York/i)).toBeInTheDocument();
        expect(getByText(/Temperature: 20 °C/i)).toBeInTheDocument();
        expect(getByText(/Condition: clear sky/i)).toBeInTheDocument();
    });

    it('should show message when no weather data is available', () => {
        const { getByText } = render(<WeatherDisplay weatherData={null} />);
        expect(getByText(/No weather data available/i)).toBeInTheDocument();
    });
});