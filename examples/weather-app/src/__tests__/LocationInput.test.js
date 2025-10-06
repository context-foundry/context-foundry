import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import LocationInput from '../components/LocationInput';

describe('LocationInput Component', () => {
  test('renders input field and button', () => {
    const mockSubmit = jest.fn();
    render(<LocationInput onSubmit={mockSubmit} />);
    
    const input = screen.getByPlaceholderText(/enter location/i);
    const button = screen.getByRole('button', { name: /get weather/i });

    expect(input).toBeInTheDocument();
    expect(button).toBeInTheDocument();
  });

  test('submits input value', () => {
    const mockSubmit = jest.fn();
    render(<LocationInput onSubmit={mockSubmit} />);

    const input = screen.getByPlaceholderText(/enter location/i);
    const button = screen.getByRole('button', { name: /get weather/i });

    fireEvent.change(input, { target: { value: 'New York' } });
    fireEvent.click(button);

    expect(mockSubmit).toHaveBeenCalledWith('New York');
  });

  test('does not submit empty input', () => {
    const mockSubmit = jest.fn();
    render(<LocationInput onSubmit={mockSubmit} />);

    const button = screen.getByRole('button', { name: /get weather/i });

    fireEvent.click(button);
    
    expect(mockSubmit).not.toHaveBeenCalled();
  });
});