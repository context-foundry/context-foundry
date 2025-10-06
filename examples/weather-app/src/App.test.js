import React from 'react';
import { render, fireEvent, screen } from '@testing-library/react';
import App from './App';

test('renders Weather App title', () => {
    render(<App />);
    const titleElement = screen.getByText(/Weather App/i);
    expect(titleElement).toBeInTheDocument();
});

test('allows users to search for weather', () => {
    render(<App />);
    const input = screen.getByPlaceholderText(/Enter location/i);
    fireEvent.change(input, { target: { value: 'New York' } });
    expect(input.value).toBe('New York');

    const button = screen.getByText(/Search/i);
    fireEvent.click(button);
    
    const weatherInfo = screen.getByText(/New York/i);
    expect(weatherInfo).toBeInTheDocument();
});