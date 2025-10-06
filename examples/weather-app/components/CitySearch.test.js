import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import CitySearch from './CitySearch';
import { WeatherContext } from '../App';

const mockFetchWeather = jest.fn();
const mockSetCity = jest.fn();

test('renders CitySearch component and handle city input', () => {
  render(
    <WeatherContext.Provider value={{ city: '', setCity: mockSetCity, fetchWeather: mockFetchWeather }}>
      <CitySearch />
    </WeatherContext.Provider>
  );

  const inputElement = screen.getByPlaceholderText(/Enter city/i);
  fireEvent.change(inputElement, { target: { value: 'London' } });

  expect(mockSetCity).toHaveBeenCalledWith('London');
  
  const buttonElement = screen.getByText(/Get Weather/i);
  fireEvent.click(buttonElement);

  expect(mockFetchWeather).toHaveBeenCalledWith('London');
});