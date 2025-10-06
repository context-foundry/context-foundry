import React from 'react';
import { render, screen } from '@testing-library/react';
import Forecast from './Forecast';

test('renders forecast information', () => {
    const mockData = [
        { date: '2023-10-01', day: { maxtemp: 20, mintemp: 10, condition: { text: 'Sunny' } } },
        { date: '2023-10-02', day: { maxtemp: 22, mintemp: 11, condition: { text: 'Cloudy' } } },
    ];
    
    render(<Forecast data={mockData} />);
    
    expect(screen.getByText(/Date: 2023-10-01/i)).toBeInTheDocument();
    expect(screen.getByText(/Max Temp: 20°C/i)).toBeInTheDocument();
    expect(screen.getByText(/Min Temp: 10°C/i)).toBeInTheDocument();
    expect(screen.getByText(/Condition: Sunny/i)).toBeInTheDocument();
});