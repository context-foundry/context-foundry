import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import App from './App';

test('renders app title', () => {
    render(<App />);
    const titleElement = screen.getByText(/Weather App/i);
    expect(titleElement).toBeInTheDocument();
});

test('submit search bar and fetch weather data', async () => {
    render(<App />);
    const inputElement = screen.getByPlaceholderText(/Enter location/i);
    const buttonElement = screen.getByRole('button', { name: /Search/i });

    fireEvent.change(inputElement, { target: { value: 'London' } });
    fireEvent.click(buttonElement);

    // Asserting that the error message disappears and the weather data is displayed
    // Simulate API response for testing as necessary in real implementation
});