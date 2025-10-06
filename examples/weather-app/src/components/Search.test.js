import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import Search from './Search';

test('it calls onSearch with the input value when submitted', () => {
    const handleSearch = jest.fn();
    render(<Search onSearch={handleSearch} />);
    
    const input = screen.getByPlaceholderText('Enter location');
    fireEvent.change(input, { target: { value: 'London' } });
    fireEvent.submit(screen.getByRole('form'));

    expect(handleSearch).toHaveBeenCalledWith('London');
});