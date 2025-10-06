import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';
import { WeatherProvider } from './store/weatherStore';

test('renders the main App components', () => {
  render(
    <WeatherProvider>
      <App />
    </WeatherProvider>
  );
  expect(screen.getByText(/Weather App/i)).toBeInTheDocument();
});