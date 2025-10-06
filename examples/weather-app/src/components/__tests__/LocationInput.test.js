import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import LocationInput from '../LocationInput';

describe('LocationInput Component', () => {
    it('should call onLocationChange when input changes', () => {
        const mockLocationChange = jest.fn();
        const { getByPlaceholderText } = render(<LocationInput location="" onLocationChange={mockLocationChange} onFetchWeather={() => {}} />);
        const input = getByPlaceholderText(/enter a location/i);
        
        fireEvent.change(input, { target: { value: 'New York' } });
        
        expect(mockLocationChange).toHaveBeenCalledWith('New York');
    });

    it('should call onFetchWeather when form is submitted', () => {
        const mockFetchWeather = jest.fn();
        const { getByText } = render(<LocationInput location="" onLocationChange={() => {}} onFetchWeather={mockFetchWeather} />);
        
        fireEvent.click(getByText(/get weather/i));
        
        expect(mockFetchWeather).toHaveBeenCalled();
    });
});