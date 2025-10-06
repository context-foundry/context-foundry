// Tests for WeatherDisplay component
import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherDisplay from './WeatherDisplay';
import { fetchWeatherData } from '../services/api';

// Mock the fetchWeatherData function
jest.mock('../services/api');

describe('WeatherDisplay', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });

    test('displays weather data on successful fetch', async () => {
        fetchWeatherData.mockResolvedValueOnce({
            name: 'London',
            main: { temp: 15 },
            weather: [{ description: 'Clear sky' }],
        });
        
        render(<WeatherDisplay city="London" />);
        
        expect(await screen.findByText(/London/i)).toBeInTheDocument();
        expect(await screen.findByText(/15 °C/i)).toBeInTheDocument();
        expect(await screen.findByText(/Clear sky/i)).toBeInTheDocument();
    });

    test('displays an error message on fetch failure', async () => {
        fetchWeatherData.mockRejectedValueOnce(new Error('City not found'));

        render(<WeatherDisplay city="InvalidCity" />);

        expect(await screen.findByText(/City not found/i)).toBeInTheDocument();
    });
});