import React from 'react';
import { render, fireEvent, screen } from '@testing-library/react';
import App from './App';
import api from './services/api';

jest.mock('./services/api');

describe('App Component', () => {
    it('fetches weather data and displays it', async () => {
        const mockWeatherData = {
            name: 'London',
            main: { temp: 15, humidity: 80 },
            weather: [{ description: 'clear sky' }],
            wind: { speed: 5 },
        };
        
        api.getWeatherData.mockResolvedValue(mockWeatherData);
        
        render(<App />);
        
        // Simulate user typing in the search bar
        fireEvent.change(screen.getByPlaceholderText('Enter city name'), { target: { value: 'London' } });
        
        // Simulate submitting the form
        fireEvent.click(screen.getByText('Search'));
        
        // Wait for data to be displayed
        expect(await screen.findByText(/Weather for London/i)).toBeInTheDocument();
        expect(screen.getByText(/Temperature: 15 °C/i)).toBeInTheDocument();
        expect(screen.getByText(/Condition: clear sky/i)).toBeInTheDocument();
    });
    
    it('handles fetch error', async () => {
        api.getWeatherData.mockRejectedValue(new Error('Fetch failed'));

        render(<App />);
        
        fireEvent.change(screen.getByPlaceholderText('Enter city name'), { target: { value: 'InvalidCity' } });
        fireEvent.click(screen.getByText('Search'));

        expect(await screen.findByText(/No data available. Please search for a city./i)).toBeInTheDocument();
    });
});