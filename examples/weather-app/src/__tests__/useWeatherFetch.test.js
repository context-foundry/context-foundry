import { renderHook } from '@testing-library/react-hooks';
import useWeatherFetch from '../hooks/useWeatherFetch';

global.fetch = jest.fn(() =>
    Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ name: 'Test City', main: { temp: 20 } }),
    })
);

describe('useWeatherFetch', () => {
    it('should fetch weather data successfully', async () => {
        const { result, waitForNextUpdate } = renderHook(() => useWeatherFetch('Test City'));

        await waitForNextUpdate();

        expect(result.current.loading).toBe(false);
        expect(result.current.weatherData).toEqual({ name: 'Test City', main: { temp: 20 } });
    });

    it('should handle fetch errors', async () => {
        fetch.mockImplementationOnce(() =>
            Promise.resolve({
                ok: false,
                json: () => Promise.resolve({}),
            })
        );

        const { result, waitForNextUpdate } = renderHook(() => useWeatherFetch('Invalid City'));

        await waitForNextUpdate();

        expect(result.current.loading).toBe(false);
        expect(result.current.error).toBe('Failed to fetch weather data');
    });

    it('should not fetch data if no city is provided', () => {
        const { result } = renderHook(() => useWeatherFetch(''));

        expect(result.current.loading).toBe(true);
        expect(result.current.weatherData).toBeNull();
    });
});