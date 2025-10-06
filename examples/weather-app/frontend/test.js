// Basic test for the app.js functionality
describe('Weather App Tests', () => {
    it('should fetch weather data for a valid city', async () => {
        const city = 'London';
        const data = await fetchWeather(city);
        expect(data).toHaveProperty('main');
        expect(data.name).toBe(city);
    });

    it('should display an error for an invalid city', async () => {
        const city = 'InvalidCityName';
        await expect(fetchWeather(city)).rejects.toThrow('City not found');
    });
});