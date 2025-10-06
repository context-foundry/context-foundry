import React from 'react';
import { render, screen } from '@testing-library/react';
import WeatherDisplay from './WeatherDisplay';
import * as weatherService from '../services/weatherService';

jest.mock('../services/weatherService');

describe('WeatherDisplay', () => {
  test('displays error message when city is empty', () => {
    render(<WeatherDisplay city="" />);
    expect(screen.getByText(/please provide a valid city name/i)).toBeInTheDocument();
  });

  test('displays error when API fetch fails', async () => {
    weatherService.fetchWeatherData.mockRejectedValue(new Error('API fetch error'));
    
    render(<WeatherDisplay city="UnknownCity" />);
    expect(await screen.findByText(/failed to fetch weather data/i)).toBeInTheDocument();
  });

  test('displays weather information when API fetch succeeds', async () => {
    const mockWeatherData = {
      name: 'Test City',
      main: { temp: 20 },
      weather: [{ description: 'clear sky' }]
    };
    weatherService.fetchWeatherData.mockResolvedValue(mockWeatherData);
    
    render(<WeatherDisplay city="Test City" />);
    expect(await screen.findByText(/weather in test city/i)).toBeInTheDocument();
    expect(screen.getByText(/temperature: 20°c/i)).toBeInTheDocument();
    expect(screen.getByText(/condition: clear sky/i)).toBeInTheDocument();
  });
});