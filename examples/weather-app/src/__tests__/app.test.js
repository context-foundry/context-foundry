// Tests for the main application component.
// This ensures rendering behavior and basic functionality.

import React from 'react';
import { render } from '@testing-library/react';
import App from '../app';

describe('App Component', () => {
  test('renders without crashing', () => {
    const { getByText } = render(<App />);
    expect(getByText(/Weather App/i)).toBeInTheDocument();
  });

  test('includes the SearchBar and WeatherDisplay', () => {
    const { container } = render(<App />);
    expect(container.querySelector('input[type="text"]')).toBeInTheDocument();
    expect(container.querySelector('.weather-display')).toBeInTheDocument();
  });
});