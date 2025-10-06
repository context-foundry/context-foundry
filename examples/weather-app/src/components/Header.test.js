import React from 'react';
import { render } from '@testing-library/react';
import Header from './Header';

test('renders header with title and subtitle', () => {
  const { getByText } = render(<Header />);
  expect(getByText(/Weather App/i)).toBeInTheDocument();
  expect(getByText(/Get real-time weather updates/i)).toBeInTheDocument();
});