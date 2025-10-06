import React from 'react';
import { render } from '@testing-library/react';
import WeatherForecast from './WeatherForecast';

test('renders WeatherForecast with multiple WeatherCards', () => {
    const forecastData = [
        { city: 'City 1', temperature: '20', condition: 'Rainy', icon: 'url1' },
        { city: 'City 2', temperature: '25', condition: 'Sunny', icon: 'url2' },
    ];

    const { getByText } = render(<WeatherForecast forecast={forecastData} />);

    expect(getByText(/City 1/i)).toBeInTheDocument();
    expect(getByText(/City 2/i)).toBeInTheDocument();
});