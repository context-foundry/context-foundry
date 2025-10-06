import { fetchCurrentWeather, fetchWeatherForecast } from './weatherApi';

// Mocking the fetch API
global.fetch = jest.fn();

describe('Weather API', () => {
    afterEach(() => {
        jest.clearAllMocks(); // Clear mock calls between tests
    });

    test('fetchCurrentWeather should return weather data for a valid city', async () => {
        // Given
        const cityName = 'London';
        const mockWeatherData = { weather: [{ description: 'clear sky' }], main: { temp: 15 } };
        fetch.mockResolvedValueOnce({
            ok: true,
            json: jest.fn().mockResolvedValueOnce(mockWeatherData),
        });

        // When
        const data = await fetchCurrentWeather(cityName);

        // Then
        expect(fetch).toHaveBeenCalledWith(`https://api.openweathermap.org/data/2.5/weather?q=${cityName}&appid=${process.env.REACT_APP_WEATHER_API_KEY}&units=metric`);
        expect(data).toEqual(mockWeatherData);
    });

    test('fetchCurrentWeather should throw an error for an invalid city', async () => {
        // Given
        const cityName = 'InvalidCity';
        fetch.mockResolvedValueOnce({ ok: false });

        // When / Then
        await expect(fetchCurrentWeather(cityName)).rejects.toThrow('Unable to fetch current weather data.');
    });

    test('fetchWeatherForecast should return forecast data for a valid city', async () => {
        // Given
        const cityName = 'London';
        const mockForecastData = { list: [{ main: { temp: 14 } }, { main: { temp: 15 } }] };
        fetch.mockResolvedValueOnce({
            ok: true,
            json: jest.fn().mockResolvedValueOnce(mockForecastData),
        });

        // When
        const data = await fetchWeatherForecast(cityName);

        // Then
        expect(fetch).toHaveBeenCalledWith(`https://api.openweathermap.org/data/2.5/forecast?q=${cityName}&appid=${process.env.REACT_APP_WEATHER_API_KEY}&units=metric`);
        expect(data).toEqual(mockForecastData);
    });

    test('fetchWeatherForecast should throw an error for an invalid city', async () => {
        // Given
        const cityName = 'InvalidCity';
        fetch.mockResolvedValueOnce({ ok: false });

        // When / Then
        await expect(fetchWeatherForecast(cityName)).rejects.toThrow('Unable to fetch weather forecast data.');
    });
});