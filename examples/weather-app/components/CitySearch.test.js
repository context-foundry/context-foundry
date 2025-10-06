import React from 'react';
import { render, screen } from '@testing-library/react';
import CitySearch from './CitySearch';

test('renders input for city search', () => {
    const mockOnCityChange = jest.fn();
    render(<CitySearch onCityChange={mockOnCityChange} />);
    const inputElement = screen.getByPlaceholderText(/enter city/i);
    expect(inputElement).toBeInTheDocument();
});

test('calls onCityChange prop when input value changes', () => {
    const mockOnCityChange = jest.fn();
    render(<CitySearch onCityChange={mockOnCityChange} />);
    const inputElement = screen.getByPlaceholderText(/enter city/i);
    
    inputElement.value = 'New York';
    inputElement.dispatchEvent(new Event('input'));

    expect(mockOnCityChange).toHaveBeenCalledWith('New York');
});