describe('Weather App', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <div id="app">
                <form id="weatherForm">
                    <input type="text" id="cityInput" value="London">
                    <button type="submit">Get Weather</button>
                </form>
                <div id="weather"></div>
            </div>
        `;
    });

    test('fetchWeather function returns weather data for valid city', async () => {
        const data = await fetchWeather('London');
        expect(data).toHaveProperty('name', 'London');
    });

    test('displayWeather function updates the DOM correctly', () => {
        const mockData = {
            name: 'London',
            main: { temp: 15 },
            weather: [{ description: 'clear sky' }]
        };
        
        displayWeather(mockData);
        const weatherContainer = document.getElementById('weather');
        expect(weatherContainer.innerHTML).toContain('Weather in London');
        expect(weatherContainer.innerHTML).toContain('Temperature: 15 °C');
        expect(weatherContainer.innerHTML).toContain('Condition: clear sky');
    });

    test('handleFormSubmit function shows alert for empty input', () => {
        const event = new Event('submit');
        const cityInput = document.getElementById('cityInput');
        cityInput.value = ''; // empty value

        handleFormSubmit(event);
        expect(alert).toHaveBeenCalledWith('Please enter a city name');
    });
});