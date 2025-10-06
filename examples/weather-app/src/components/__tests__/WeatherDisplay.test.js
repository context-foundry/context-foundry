import React from 'react';
import { render } from '@testing-library/react';
import WeatherDisplay from '../WeatherDisplay';

test('renders WeatherDisplay with correct data', () => {
    const { getByText } = render(
        <WeatherDisplay city="New York" temperature={15} description="Sunny" />
    );

    expect(getByText(/new york/i)).toBeInTheDocument();
    expect(getByText(/temperature: 15°c/i)).toBeInTheDocument();
    expect(getByText(/description: sunny/i)).toBeInTheDocument();
});