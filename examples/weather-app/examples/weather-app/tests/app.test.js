// Test suite for Weather App functionality
// Requires an appropriate JavaScript testing framework like Jest or Mocha

/**
 * Mock fetch for testing
 * @param {string} url The mock URL to simulate API call
 * @returns {Promise} Simulated response
 */
global.fetch = (url) => {
    const mockResponse = {
        status: 200,
        json: async () => ({
            name: 'London',
            sys: { country: 'GB' },
            main: { temp: 15 },
            weather: [{ description: 'clear sky' }]
        })
    };
    return Promise.resolve(mockResponse);
};

test('fetchWeather should fetch and display weather data', async () => {
    document.body.innerHTML = `
        <section id="weather-info" class="hidden">
            <h2 id="location-name"></h2>
            <p id="temperature"></p>
            <p id="description"></p>
        </section>
    `;

    await fetchWeather('London');

    expect(document.getElementById('location-name').textContent).toBe('Location: London, GB');
    expect(document.getElementById('temperature').textContent).toBe('Temperature: 15 °C');
    expect(document.getElementById('description').textContent).toBe('Description: clear sky');
});