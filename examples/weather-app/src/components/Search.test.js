import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import Search from './Search';

test('Search component calls onSearch with correct input', () => {
    const handleSearch = jest.fn();
    const { getByPlaceholderText, getByText } = render(<Search onSearch={handleSearch} />);
    
    const input = getByPlaceholderText('Enter a city');
    const button = getByText('Search');

    fireEvent.change(input, { target: { value: 'New York' } });
    fireEvent.click(button);
    
    expect(handleSearch).toHaveBeenCalledWith('New York');
});