import React from 'react';
import { render } from '@testing-library/react';
import WeatherForecast from './WeatherForecast';

describe('WeatherForecast Component', () => {
  it('renders correctly with forecast data', () => {
    const mockForecast = [
      { dt_txt: '2023-10-20 12:00:00', main: { temp: 20 }, weather: [{ description: 'cloudy' }] },
      { dt_txt: '2023-10-21 12:00:00', main: { temp: 22 }, weather: [{ description: 'sunny' }] }
    ];
    global.fetch = jest.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ list: mockForecast }),
      })
    );
    const { getByText } = render(<WeatherForecast location="New York" />);
    expect(getByText(/5-Day Forecast/i)).toBeInTheDocument();
    expect(getByText(/2023-10-20 12:00:00/i)).toBeInTheDocument();
    expect(getByText(/Temperature: 20 °C, cloudy/i)).toBeInTheDocument();
  });
});