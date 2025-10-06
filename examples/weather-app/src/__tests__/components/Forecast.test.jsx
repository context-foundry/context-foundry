import React from 'react';
import { render } from '@testing-library/react';
import Forecast from '../../components/Forecast';
import { WeatherContext } from '../../context/WeatherContext';

describe('Forecast Component', () => {
  const mockData = [
    { date: '2023-10-18', temperature: 22, description: 'Sunny', icon: 'sun.png' },
    { date: '2023-10-19', temperature: 18, description: 'Cloudy', icon: 'cloud.png' },
    { date: '2023-10-20', temperature: 15, description: 'Rainy', icon: 'rain.png' },
    { date: '2023-10-21', temperature: 20, description: 'Windy', icon: 'wind.png' },
    { date: '2023-10-22', temperature: 23, description: 'Sunny', icon: 'sun.png' },
  ];

  it('renders the forecast title correctly', () => {
    const { getByText } = render(
      <WeatherContext.Provider value={{ forecastData: mockData }}>
        <Forecast />
      </WeatherContext.Provider>
    );

    expect(getByText('5-Day Weather Forecast')).toBeInTheDocument();
  });

  it('renders weather cards for each day in the forecast', () => {
    const { getAllByTestId } = render(
      <WeatherContext.Provider value={{ forecastData: mockData }}>
        <Forecast />
      </WeatherContext.Provider>
    );

    const weatherCards = getAllByTestId('weather-card');
    expect(weatherCards.length).toBe(mockData.length);
  });

  it('renders message when no forecast data is available', () => {
    const { getByText } = render(
      <WeatherContext.Provider value={{ forecastData: [] }}>
        <Forecast />
      </WeatherContext.Provider>
    );

    expect(getByText('No forecast data available.')).toBeInTheDocument();
  });
});