// src/services/__tests__/weatherService.test.js
import axios from 'axios';
import { getWeatherByCity } from '../weatherService';

jest.mock('axios');

describe('getWeatherByCity', () => {
    it('should return weather data when valid city is provided', async () => {
        const city = 'London';
        const mockWeatherData = {
            weather: [{ description: 'clear sky' }],
            main: { temp: 15 },
        };

        axios.get.mockResolvedValueOnce({ status: 200, data: mockWeatherData });

        const data = await getWeatherByCity(city);
        expect(data).toEqual(mockWeatherData);
    });

    it('should throw an error when city is not found', async () => {
        const city = 'InvalidCity';
        axios.get.mockRejectedValueOnce({
            response: {
                status: 404,
                data: { message: 'city not found' },
            },
        });

        await expect(getWeatherByCity(city)).rejects.toThrow('Error: 404 - city not found');
    });

    it('should throw an error when no response is received', async () => {
        const city = 'NoResponseCity';
        axios.get.mockRejectedValueOnce({ request: {} });

        await expect(getWeatherByCity(city)).rejects.toThrow('Error: No response received from the weather service.');
    });

    it('should throw an error for other request errors', async () => {
        const city = 'AnotherCity';
        axios.get.mockRejectedValueOnce(new Error('Network Error'));

        await expect(getWeatherByCity(city)).rejects.toThrow('Error: Network Error');
    });
});