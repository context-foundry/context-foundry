// Test file to verify the app's responsiveness (Example: Using Jest)
test('Check if temperature and condition are correctly updated', () => {
    document.body.innerHTML = `
        <div class="weather-card" id="weather-card">
            <div class="weather-details">
                <div id="temperature">Temp: 20°C</div>
                <div id="condition">Condition: Sunny</div>
            </div>
        </div>
    `;
    
    updateWeather();
    
    const temperature = document.getElementById('temperature').textContent;
    const condition = document.getElementById('condition').textContent;

    expect(temperature).toBe('Temp: 20°C');
    expect(condition).toBe('Condition: Sunny');
});