// store.test.js

import { store } from '../store';

describe('Weather App Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    store.setCity('');
    store.setWeatherData(null);
    store.setLoading();
    store.setError(null);
  });

  test('setCity updates the city in state', () => {
    store.setCity('New York');
    expect(store.getState().city).toBe('New York');
  });

  test('setWeatherData updates weather data and loading state', () => {
    const weatherData = { temperature: 75, condition: 'Sunny' };
    store.setWeatherData(weatherData);
    expect(store.getState().weatherData).toEqual(weatherData);
    expect(store.getState().loading).toBe(false);
  });

  test('setLoading sets loading state correctly', () => {
    store.setLoading();
    expect(store.getState().loading).toBe(true);
    expect(store.getState().error).toBe(null); // Error should be reset
  });

  test('setError sets error state and stops loading', () => {
    store.setLoading(); // set loading first
    store.setError('Fetch failed');
    expect(store.getState().loading).toBe(false);
    expect(store.getState().error).toBe('Fetch failed');
  });

  test('getState returns the current state', () => {
    const currentState = store.getState();
    expect(currentState).toEqual({
      city: '',
      weatherData: null,
      loading: false,
      error: null,
    });
  });
});