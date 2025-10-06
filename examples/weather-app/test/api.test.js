// api.test.js - Unit tests for the API module
import { getWeatherData } from '../api.js';

describe('getWeatherData', () => {
    test('fetches weather data successfully', async () => {
        const data = await getWeatherData('London');
        expect(data).toHaveProperty('weather');
        expect(data).toHaveProperty('main');
    });

    test('throws an error when city is not found', async () => {
        await expect(getWeatherData('InvalidCity')).rejects.toThrow('Unable to fetch weather data');
    });
});