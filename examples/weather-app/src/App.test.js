import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders loading message initially', () => {
    render(<App />);
    const loadingMessage = screen.getByText(/loading/i);
    expect(loadingMessage).toBeInTheDocument();
});

// Additional tests to ensure weather data is displayed could be added here.