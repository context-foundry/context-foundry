import weatherService from './weatherService';
import axios from 'axios';

jest.mock('axios');

describe('weatherService', () => {
  const city = 'London';
  const weatherData = {
    weather: [{ description: 'clear sky' }],
    main: { temp: 15 },
    name: city,
  };

  const forecastData = {
    list: [{ weather: [{ description: 'light rain' }], main: { temp: 12 } }],
  };

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should fetch weather data by city', async () => {
    axios.get.mockResolvedValue({ data: weatherData });

    const data = await weatherService.getWeatherByCity(city);
    expect(data).toEqual(weatherData);
    expect(axios.get).toHaveBeenCalledWith(
      expect.stringContaining('/weather'),
      expect.objectContaining({
        params: expect.objectContaining({
          q: city,
          appid: expect.any(String),
          units: 'metric',
        }),
      })
    );
  });

  it('should fetch forecast data by city', async () => {
    axios.get.mockResolvedValue({ data: forecastData });

    const data = await weatherService.getForecastByCity(city);
    expect(data).toEqual(forecastData);
    expect(axios.get).toHaveBeenCalledWith(
      expect.stringContaining('/forecast'),
      expect.objectContaining({
        params: expect.objectContaining({
          q: city,
          appid: expect.any(String),
          units: 'metric',
        }),
      })
    );
  });

  it('should handle errors when fetching weather data', async () => {
    axios.get.mockRejectedValue(new Error('Network Error'));

    await expect(weatherService.getWeatherByCity(city)).rejects.toThrow('Network Error');
  });

  it('should handle errors when fetching forecast data', async () => {
    axios.get.mockRejectedValue(new Error('Network Error'));

    await expect(weatherService.getForecastByCity(city)).rejects.toThrow('Network Error');
  });
});