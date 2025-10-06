import { fetchWeatherData } from '../weatherService';

describe('fetchWeatherData', () => {
    it('should fetch weather data for valid latitude and longitude', async () => {
        const data = await fetchWeatherData({ latitude: 35.6895, longitude: 139.6917 });
        expect(data).toHaveProperty('main');
    });

    it('should throw an error for invalid location', async () => {
        await expect(fetchWeatherData({ latitude: 'invalid', longitude: 'invalid' })).rejects.toThrow('Failed to fetch weather data');
    });
});