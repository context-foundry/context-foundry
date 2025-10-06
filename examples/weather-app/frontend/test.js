/**
 * Test the fetchWeatherData function.
 */
async function testFetchWeatherData() {
    const testCity = 'London';
    const data = await fetchWeatherData(testCity);
    console.log(`Weather data for ${testCity}:`, data);
    if (data && data.main) {
        console.log(`Temperature in ${testCity}: ${data.main.temp} °C`);
    } else {
        console.error('No weather data found for the test city.');
    }
}

// Run the test
testFetchWeatherData();