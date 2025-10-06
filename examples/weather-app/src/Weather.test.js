import React from 'react';
import { render, screen } from '@testing-library/react';
import Weather from './Weather';

test('displays weather information', () => {
    const mockData = {
        location: { name: 'London' },
        current: { temp: 15, condition: { text: 'Clear' } },
    };

    render(<Weather data={mockData} />);
  
    expect(screen.getByText(/Location: London/i)).toBeInTheDocument();
    expect(screen.getByText(/Temperature: 15°C/i)).toBeInTheDocument();
    expect(screen.getByText(/Condition: Clear/i)).toBeInTheDocument();
});