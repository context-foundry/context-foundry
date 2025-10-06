import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { WeatherProvider, useWeather } from '../store';

const MockComponent = () => {
  const { weatherData, fetchWeatherData, loading, error } = useWeather();
  return (
    <div>
      <button onClick={() => fetchWeatherData('New York')}>Fetch Weather</button>
      {loading && <p>Loading...</p>}
      {error && <p>Error: {error}</p>}
      {weatherData && <p>{`Weather: ${JSON.stringify(weatherData)}`}</p>}
    </div>
  );
};

test('fetches weather data and handles loading and error states', async () => {
  render(
    <WeatherProvider>
      <MockComponent />
    </WeatherProvider>
  );

  // simulate fetch call
  const button = screen.getByText(/Fetch Weather/i);
  act(() => {
    button.click();
  });

  expect(screen.getByText(/Loading.../i)).toBeInTheDocument();

  // Mock implementation for the fetch function
  global.fetch = jest.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ temperature: 70, condition: 'Sunny' }),
    })
  );

  await act(async () => {
    // wait for loading to finish
    await new Promise((r) => setTimeout(r, 100));
  });

  expect(screen.getByText(/Weather:/i)).toBeInTheDocument();
  expect(screen.getByText(/"temperature":70/i)).toBeInTheDocument();
  expect(screen.getByText(/"condition":"Sunny"/i)).toBeInTheDocument();

  // Cleanup mock
  global.fetch.mockClear();
});