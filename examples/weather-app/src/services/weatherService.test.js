import { fetchWeatherData } from './weatherService';
import axios from 'axios';

jest.mock('axios');

describe('Weather Service', () => {
  test('fetchWeatherData retrieves weather data', async () => {
    const location = 'New York';
    const data = { location: { name: location }, current: { temperature: 20 } };

    axios.get.mockResolvedValueOnce({ data });

    const result = await fetchWeatherData(location);

    expect(result).toBe(data);
    expect(axios.get).toHaveBeenCalledWith(`https://api.weatherapi.com/v1/current.json?key=${process.env.REACT_APP_WEATHER_API_KEY}&q=${location}`);
  });
});