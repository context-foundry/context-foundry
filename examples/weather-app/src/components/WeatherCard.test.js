import React from 'react';
import { render } from '@testing-library/react';
import WeatherCard from './WeatherCard';

test('renders weather card with correct data', () => {
    const { getByText, getByAltText } = render(
        <WeatherCard 
            city="London" 
            temperature="20" 
            condition="Sunny" 
            icon="http://example.com/icon.png" 
        />
    );

    expect(getByText(/London/i)).toBeInTheDocument();
    expect(getByText(/20 °C/i)).toBeInTheDocument();
    expect(getByText(/Sunny/i)).toBeInTheDocument();
    expect(getByAltText(/Weather Icon/i)).toBeInTheDocument();
});