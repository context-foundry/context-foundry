// Actual complete test code goes here
import { fetchWeather, updateDOM, handleError } from './app.js';

describe('Weather App Tests', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <div id="weather-info"></div>
            <div id="error-message"></div>
        `;
    });

    test('fetchWeather returns data when city is valid', async () => {
        const data = await fetchWeather('London');
        expect(data).toHaveProperty('name', 'London');
    });

    test('fetchWeather throws error when city is invalid', async () => {
        await expect(fetchWeather('InvalidCity')).rejects.toThrow('City not found');
    });

    test('updateDOM updates the weather information on the page', () => {
        const weatherData = {
            name: 'London',
            main: { temp: 15, feels_like: 14 },
            weather: [{ description: 'clear sky' }],
        };
        
        updateDOM(weatherData);
        
        expect(document.getElementById('weather-info').innerHTML).toContain('Weather in London');
        expect(document.getElementById('weather-info').innerHTML).toContain('Temperature: 15 °C');
    });

    test('handleError displays error message', () => {
        handleError(new Error('City not found'));
        expect(document.getElementById('error-message').textContent).toBe('City not found');
    });
});