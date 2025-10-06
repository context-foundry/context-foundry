// frontend/test.js
describe('Weather App Input Validation', () => {
    let cityInput;
    let errorMessage;

    beforeEach(() => {
        document.body.innerHTML = `
            <form id="city-form">
                <input type="text" id="city-input">
                <p id="error-message" class="error-message"></p>
            </form>
        `;
        cityInput = document.getElementById('city-input');
        errorMessage = document.getElementById('error-message');
        // Attach the event listener for testing
        document.getElementById('city-form').addEventListener('submit', (event) => {
            event.preventDefault();
            const cityName = cityInput.value.trim();
            if (validateCityName(cityName)) {
                errorMessage.textContent = '';
            } else {
                errorMessage.textContent = 'Please enter a valid city name.';
            }
        });
    });

    test('validates city name with letters', () => {
        cityInput.value = 'New York';
        document.getElementById('city-form').dispatchEvent(new Event('submit'));
        expect(errorMessage.textContent).toBe('');
    });

    test('invalidates empty city name', () => {
        cityInput.value = '';
        document.getElementById('city-form').dispatchEvent(new Event('submit'));
        expect(errorMessage.textContent).toBe('Please enter a valid city name.');
    });

    test('invalidates city names with special characters', () => {
        cityInput.value = 'New@York';
        document.getElementById('city-form').dispatchEvent(new Event('submit'));
        expect(errorMessage.textContent).toBe('Please enter a valid city name.');
    });
});