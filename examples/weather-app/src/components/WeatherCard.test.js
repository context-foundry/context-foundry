import React from 'react';
import { render } from '@testing-library/react';
import WeatherCard from './WeatherCard';

test('WeatherCard displays correct information', () => {
    const { getByText } = render(<WeatherCard city="Los Angeles" temperature={25} condition="Sunny" />);
    
    expect(getByText('Los Angeles')).toBeInTheDocument();
    expect(getByText('25°C')).toBeInTheDocument();
    expect(getByText('Sunny')).toBeInTheDocument();
});