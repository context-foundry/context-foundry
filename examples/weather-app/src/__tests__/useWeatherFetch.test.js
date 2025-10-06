import { renderHook, act } from '@testing-library/react-hooks';
import useWeatherFetch from '../hooks/useWeatherFetch';

describe('useWeatherFetch Hook', () => {
  beforeEach(() => {
    fetch.resetMocks();
  });

  test('returns loading, data and error states', async () => {
    fetch.mockResponseOnce(JSON.stringify({ location: 'New York', temperature: 25, condition: 'Sunny' }));

    const { result, waitForNextUpdate } = renderHook(() => useWeatherFetch('New York'));

    expect(result.current.loading).toBe(true);
    expect(result.current.weatherData).toBeNull();
    expect(result.current.error).toBeNull();

    await waitForNextUpdate();

    expect(result.current.loading).toBe(false);
    expect(result.current.weatherData).toEqual({ location: 'New York', temperature: 25, condition: 'Sunny' });
    expect(result.current.error).toBeNull();
  });

  test('sets error on fetch failure', async () => {
    fetch.mockRejectOnce(new Error('Failed to fetch'));

    const { result, waitForNextUpdate } = renderHook(() => useWeatherFetch('Invalid location'));

    expect(result.current.loading).toBe(true);
    
    await waitForNextUpdate();

    expect(result.current.loading).toBe(false);
    expect(result.current.weatherData).toBeNull();
    expect(result.current.error).toBe('Failed to fetch');
  });
});