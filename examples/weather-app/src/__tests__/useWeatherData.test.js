import { renderHook, act } from '@testing-library/react-hooks';
import useWeatherData from '../hooks/useWeatherData';

// Mock the fetch API calls
global.fetch = jest.fn();

describe('useWeatherData Hook', () => {
  const mockCityName = 'London';
  const mockWeatherResponse = {
    weather: [{ description: 'clear sky' }],
    main: { temp: 22 },
    name: 'London',
  };

  beforeEach(() => {
    fetch.mockClear();
  });

  test('should fetch weather data successfully', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockWeatherResponse,
    });

    const { result, waitForNextUpdate } = renderHook(() => useWeatherData(mockCityName));

    expect(result.current.weatherData).toBe(null);
    expect(result.current.loading).toBe(true);
    expect(result.current.error).toBe(null);

    await waitForNextUpdate();

    expect(fetch).toHaveBeenCalledWith(
      `https://api.openweathermap.org/data/2.5/weather?q=${mockCityName}&appid=${process.env.REACT_APP_WEATHER_API_KEY}&units=metric`
    );
    expect(result.current.weatherData).toEqual(mockWeatherResponse);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(null);
  });

  test('should handle API errors gracefully', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      statusText: 'Not Found',
    });

    const { result, waitForNextUpdate } = renderHook(() => useWeatherData(mockCityName));

    expect(result.current.weatherData).toBe(null);
    expect(result.current.loading).toBe(true);
    expect(result.current.error).toBe(null);

    await waitForNextUpdate();

    expect(result.current.weatherData).toBe(null);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe('Error fetching weather data: Not Found');
  });

  test('should return an error when no city is provided', async () => {
    const { result } = renderHook(() => useWeatherData());

    expect(result.current.weatherData).toBe(null);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe('City is required to fetch weather data.');
  });
});