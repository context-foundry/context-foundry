import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import Search from './Search';

test('calls onSearch with the city name when form is submitted', () => {
  const handleSearch = jest.fn();
  const { getByPlaceholderText, getByText } = render(<Search onSearch={handleSearch} />);

  const input = getByPlaceholderText(/Enter city/i);
  fireEvent.change(input, { target: { value: 'New York' } });
  fireEvent.click(getByText(/Search/i));

  expect(handleSearch).toHaveBeenCalledWith('New York');
});