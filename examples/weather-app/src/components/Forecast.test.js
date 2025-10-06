import React from 'react';
import { render } from '@testing-library/react';
import Forecast from './Forecast';

test('Forecast displays correct number of forecast items', () => {
    const sampleForecast = [
        { date: '2023-10-01', temperature: 22 },
        { date: '2023-10-02', temperature: 20 },
        { date: '2023-10-03', temperature: 19 },
        { date: '2023-10-04', temperature: 21 },
        { date: '2023-10-05', temperature: 23 },
    ];

    const { getByText } = render(<Forecast forecast={sampleForecast} />);

    sampleForecast.forEach(({ date, temperature }) => {
        expect(getByText(date)).toBeInTheDocument();
        expect(getByText(`${temperature}°C`)).toBeInTheDocument();
    });
});