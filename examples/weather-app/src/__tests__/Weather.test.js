// Test for the Weather component
import React from 'react';
import { render, screen } from '@testing-library/react';
import Weather from '../components/Weather';
import axios from 'axios';

jest.mock('axios');

describe('Weather Component', () => {
  it('renders loading state initially', () => {
    render(<Weather />);
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it('renders weather data after fetch', async () => {
    const weatherData = {
      name: 'London',
      weather: [{ description: 'clear sky' }],
      main: { temp: 300 }
    };
    
    axios.get.mockResolvedValueOnce({ data: weatherData });

    render(<Weather />);
    expect(await screen.findByText(/London/i)).toBeInTheDocument();
    expect(screen.getByText(/clear sky/i)).toBeInTheDocument();
    expect(screen.getByText(/Temperature: 27 °C/i)).toBeInTheDocument();
  });
});