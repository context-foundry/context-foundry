import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import LocationInput from '../LocationInput';

test('renders LocationInput and submits the value', () => {
    const mockOnSubmit = jest.fn();
    const { getByPlaceholderText, getByText } = render(<LocationInput onSubmit={mockOnSubmit} />);

    const input = getByPlaceholderText(/enter location/i);
    const button = getByText(/get weather/i);

    fireEvent.change(input, { target: { value: 'New York' } });
    fireEvent.click(button);

    expect(mockOnSubmit).toHaveBeenCalledWith('New York');
    expect(input.value).toBe(''); // input should be cleared after submission
});