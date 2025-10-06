import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import SearchBar from '../components/SearchBar';

describe('SearchBar Component', () => {
  it('renders properly', () => {
    const { getByPlaceholderText, getByRole } = render(<SearchBar onSearch={jest.fn()} />);
    expect(getByPlaceholderText('Enter city name...')).toBeInTheDocument();
    expect(getByRole('button', { name: /search/i })).toBeInTheDocument();
  });

  it('handles input changes', () => {
    const { getByPlaceholderText } = render(<SearchBar onSearch={jest.fn()} />);
    const input = getByPlaceholderText('Enter city name...');
    fireEvent.change(input, { target: { value: 'New York' } });
    expect(input).toHaveValue('New York');
  });

  it('submits the search query', () => {
    const mockOnSearch = jest.fn();
    const { getByPlaceholderText, getByRole } = render(<SearchBar onSearch={mockOnSearch} />);

    const input = getByPlaceholderText('Enter city name...');
    const button = getByRole('button', { name: /search/i });

    fireEvent.change(input, { target: { value: 'New York' } });
    fireEvent.click(button);

    expect(mockOnSearch).toHaveBeenCalledWith('New York');
    expect(input).toHaveValue(''); // Input should be cleared after submission
  });

  it('does not submit an empty query', () => {
    const mockOnSearch = jest.fn();
    const { getByRole } = render(<SearchBar onSearch={mockOnSearch} />);

    const button = getByRole('button', { name: /search/i });
    fireEvent.click(button);

    expect(mockOnSearch).not.toHaveBeenCalled();
  });
});