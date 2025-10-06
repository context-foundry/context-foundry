import { fetchWeatherData } from './apiService';
import axios from 'axios';

jest.mock('axios');

describe('fetchWeatherData', () => {
    it('should fetch weather data successfully', async () => {
        const city = 'London';
        const mockData = {
            weather: [{ description: 'clear sky' }],
            main: { temp: 15 },
        };
        
        axios.get.mockResolvedValueOnce({ status: 200, data: mockData });
        
        const data = await fetchWeatherData(city);
        expect(data).toEqual(mockData);
    });

    it('should throw an error when the API returns a status other than 200', async () => {
        const city = 'InvalidCity';
        
        axios.get.mockResolvedValueOnce({ status: 404, data: { message: 'City not found' } });
        
        await expect(fetchWeatherData(city)).rejects.toThrow('Failed to fetch weather data');
    });

    it('should handle network errors', async () => {
        const city = 'Paris';
        
        axios.get.mockRejectedValueOnce(new Error('Network Error'));
        
        await expect(fetchWeatherData(city)).rejects.toThrow('Something went wrong!');
    });

    it('should handle errors with API message', async () => {
        const city = 'InvalidCity';
        
        axios.get.mockResolvedValueOnce({ status: 500, data: { message: 'Internal Server Error' } });
        
        await expect(fetchWeatherData(city)).rejects.toThrow('Internal Server Error');
    });
});