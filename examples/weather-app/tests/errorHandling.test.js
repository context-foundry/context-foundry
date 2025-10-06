// Sample tests for error handling in weather app

describe('Weather App Error Handling', () => {
    it('should display error message for empty input', () => {
        const searchInput = document.getElementById('search-input');
        const errorMessage = document.getElementById('error-message');

        // Simulate submitting an empty input
        searchInput.value = '';
        displayError('Please enter a valid location.');

        expect(errorMessage.textContent).toBe('Please enter a valid location.');
    });

    it('should display error message for invalid city', async () => {
        // Mock the fetch request failure
        global.fetch = jest.fn(() =>
            Promise.reject(new Error('City not found. Please try again.'))
        );

        await fetchWeather('InvalidCityName'); // Assuming this is a function that will trigger fetch

        expect(errorMessage.textContent).toBe('City not found. Please try again.');
    });
});