import { fetchWeatherData } from './weatherApi';
import axios from 'axios';

jest.mock('axios');

describe('fetchWeatherData', () => {
    it('should return weather data for valid city', async () => {
        const city = 'London';
        const weatherData = { name: 'London', main: { temp: 15 }, weather: [{ description: 'Clear' }] };

        axios.get.mockResolvedValue({ data: weatherData });

        const data = await fetchWeatherData(city);
        expect(data).toEqual(weatherData);
    });

    it('should throw an error for invalid city', async () => {
        const city = 'InvalidCity';

        axios.get.mockRejectedValue({
            response: {
                status: 404,
                data: { message: 'city not found' },
            },
        });

        await expect(fetchWeatherData(city)).rejects.toThrow('Error 404: city not found');
    });

    it('should handle network errors', async () => {
        const city = 'SomeCity';

        axios.get.mockRejectedValue({ request: {} });

        await expect(fetchWeatherData(city)).rejects.toThrow('Network error. Please try again later.');
    });

    it('should handle unexpected errors', async () => {
        const city = 'SomeCity';

        axios.get.mockRejectedValue(new Error('An unexpected error'));

        await expect(fetchWeatherData(city)).rejects.toThrow('An unexpected error occurred');
    });
});