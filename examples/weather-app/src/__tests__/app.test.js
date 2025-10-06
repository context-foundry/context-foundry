/**
 * Tests for the weather app's frontend logic
 */
import fetchMock from 'jest-fetch-mock';

fetchMock.enableMocks();

beforeEach(() => {
  fetchMock.resetMocks();
});

test("fetches weather data successfully", async () => {
  fetchMock.mockResponseOnce(
    JSON.stringify({
      name: "London",
      main: { temp: 288.15 },
      weather: [{ description: "clear sky" }]
    })
  );

  document.body.innerHTML = `
    <form id="weather-form">
      <input type="text" id="city-input" value="London">
      <button type="submit"></button>
    </form>
    <div id="result">
      <p id="weather-data"></p>
    </div>
  `;

  const event = new Event("submit", { bubbles: true });
  document.getElementById("weather-form").dispatchEvent(event);

  await new Promise((r) => setTimeout(r, 100));

  const resultText = document.getElementById("weather-data").textContent;
  expect(resultText).toContain("City: London");
  expect(resultText).toContain("Temperature: 15.00 °C");
  expect(resultText).toContain("Weather: clear sky");
});