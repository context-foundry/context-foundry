// store.test.js - Unit tests for the rendering module
import { renderWeatherData } from '../store.js';

describe('renderWeatherData', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="output"></div>';
    });

    test('renders weather data correctly', () => {
        const mockData = {
            name: 'London',
            main: { temp: 20 },
            weather: [{ description: 'clear sky' }]
        };
        renderWeatherData(mockData);
        const outputElement = document.getElementById('output');

        expect(outputElement.innerHTML).toContain('London');
        expect(outputElement.innerHTML).toContain('Temperature: 20°C');
        expect(outputElement.innerHTML).toContain('Weather: clear sky');
    });
});