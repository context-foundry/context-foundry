import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import SearchBar from './SearchBar';

test('renders search input and button', () => {
    const onSearch = jest.fn();
    render(<SearchBar onSearch={onSearch} />);

    const input = screen.getByPlaceholderText(/enter city name/i);
    const button = screen.getByRole('button', { name: /search/i });

    expect(input).toBeInTheDocument();
    expect(button).toBeInTheDocument();
});

test('calls onSearch with the input value when submitted', () => {
    const onSearch = jest.fn();
    render(<SearchBar onSearch={onSearch} />);

    const input = screen.getByPlaceholderText(/enter city name/i);
    const button = screen.getByRole('button', { name: /search/i });

    fireEvent.change(input, { target: { value: 'New York' } });
    fireEvent.click(button);

    expect(onSearch).toHaveBeenCalledWith('New York');
});