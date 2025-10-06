import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import CitySearch from './CitySearch';

test('renders CitySearch component and handles input change and submit', () => {
    const handleSearch = jest.fn();
    render(<CitySearch onSearch={handleSearch} />);

    const input = screen.getByPlaceholderText(/enter city name/i);
    const button = screen.getByText(/search/i);

    fireEvent.change(input, { target: { value: 'London' } });
    fireEvent.click(button);

    expect(handleSearch).toHaveBeenCalledWith('London');
});