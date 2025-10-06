import { fetchWeatherData } from './weather';
import axios from 'axios';

jest.mock('axios');

describe('fetchWeatherData', () => {
    it('should fetch weather data for a valid city', async () => {
        const city = 'London';
        const weatherData = {
            main: { temp: 15 },
            name: 'London',
            weather: [{ description: 'clear sky' }],
        };

        axios.get.mockResolvedValue({ data: weatherData });

        const result = await fetchWeatherData(city);

        expect(result).toEqual(weatherData);
        expect(axios.get).toHaveBeenCalledWith(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${process.env.REACT_APP_WEATHER_API_KEY}&units=metric`);
    });

    it('should throw error if city name is not provided', async () => {
        await expect(fetchWeatherData('')).rejects.toThrow('City name is required');
    });

    it('should handle errors gracefully', async () => {
        const city = 'InvalidCity';
        axios.get.mockRejectedValue(new Error('Network Error'));

        await expect(fetchWeatherData(city)).rejects.toThrow('Error fetching weather data: Network Error');
    });
});