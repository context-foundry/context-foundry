// Tests for the WeatherProvider and useWeather hook
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { WeatherProvider, useWeather } from './weatherStore';

const TestComponent = () => {
    const { weatherData, loading, error, fetchWeatherData } = useWeather();
    
    React.useEffect(() => {
        fetchWeatherData('London');
    }, [fetchWeatherData]);
    
    if (loading) return <div>Loading...</div>;
    if (error) return <div>{error}</div>;
    return <div>{weatherData ? weatherData.name : "No data"}</div>;
};

describe('Weather Store', () => {
    it('should fetch weather data', async () => {
        render(
            <WeatherProvider>
                <TestComponent />
            </WeatherProvider>
        );

        expect(screen.getByText('Loading...')).toBeInTheDocument();

        await waitFor(() => {
            expect(screen.getByText(/London/i)).toBeInTheDocument();
        });
    });

    it('should handle errors', async () => {
        global.fetch = jest.fn(() =>
            Promise.reject(new Error('Failed to fetch'))
        );

        render(
            <WeatherProvider>
                <TestComponent />
            </WeatherProvider>
        );

        await waitFor(() => {
            expect(screen.getByText(/Failed to fetch/i)).toBeInTheDocument();
        });
    });
});