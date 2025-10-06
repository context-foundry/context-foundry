// src/services/api.test.js

import { fetchWeatherByCity, fetchWeatherByCoordinates } from './api';

// Mock the global fetch function
global.fetch = jest.fn();

describe('API Service', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });

    test('fetchWeatherByCity should return weather data for valid city', async () => {
        const mockResponse = { weather: [{ description: 'clear sky' }], main: { temp: 20 } };
        fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockResponse,
        });

        const data = await fetchWeatherByCity('London');
        expect(data).toEqual(mockResponse);
        expect(fetch).toHaveBeenCalledWith(expect.stringContaining('q=London'));
    });

    test('fetchWeatherByCity should throw an error for invalid city', async () => {
        fetch.mockResolvedValueOnce({ ok: false, statusText: 'Not Found' });

        await expect(fetchWeatherByCity('InvalidCity')).rejects.toThrow('Error fetching weather data: Not Found');
    });

    test('fetchWeatherByCoordinates should return weather data for valid coordinates', async () => {
        const mockResponse = { weather: [{ description: 'clear sky' }], main: { temp: 20 } };
        fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => mockResponse,
        });

        const data = await fetchWeatherByCoordinates(51.5074, -0.1278);
        expect(data).toEqual(mockResponse);
        expect(fetch).toHaveBeenCalledWith(expect.stringContaining('lat=51.5074'));
        expect(fetch).toHaveBeenCalledWith(expect.stringContaining('lon=-0.1278'));
    });

    test('fetchWeatherByCoordinates should throw an error for invalid coordinates', async () => {
        fetch.mockResolvedValueOnce({ ok: false, statusText: 'Not Found' });

        await expect(fetchWeatherByCoordinates(999, 999)).rejects.toThrow('Error fetching weather data: Not Found');
    });
});