import React from 'react';
import { render } from '@testing-library/react';
import WeatherCard from './WeatherCard';

test('renders WeatherCard with correct data', () => {
    const { getByText, getByAltText } = render(
        <WeatherCard
            city="Sample City"
            temperature="25"
            condition="Sunny"
            icon="http://example.com/sunny.png"
        />
    );

    expect(getByText(/Sample City/i)).toBeInTheDocument();
    expect(getByText(/25/i)).toBeInTheDocument();
    expect(getByText(/Sunny/i)).toBeInTheDocument();
    expect(getByAltText(/Sunny/i)).toBeInTheDocument();
});