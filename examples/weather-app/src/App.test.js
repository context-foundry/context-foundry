import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import App from './App';

test('renders Weather App title', () => {
  render(<App />);
  const linkElement = screen.getByText(/Weather App/i);
  expect(linkElement).toBeInTheDocument();
});

test('fetches weather data and displays it', async () => {
  render(<App />);
  const input = screen.getByPlaceholderText(/Enter city/i);
  fireEvent.change(input, { target: { value: 'London' } });
  fireEvent.click(screen.getByText(/Get Weather/i));
  
  // Replace with appropriate match for your mock weather data
  expect(await screen.findByText(/London/i)).toBeInTheDocument();
});