/**
 * Tests for app.js - Weather App functionality
 */

import { fetchWeatherData, parseWeatherData } from "../js/utils.js";

jest.mock("../js/utils.js");

describe("Weather App integration", () => {
  document.body.innerHTML = `
    <form id="weather-form">
      <input id="city-input" type="text" />
      <button type="submit">Search</button>
    </form>
    <div id="result"></div>
    <div id="error-message"></div>
  `;

  const cityInput = document.getElementById("city-input");
  const resultContainer = document.getElementById("result");
  const errorContainer = document.getElementById("error-message");
  const form = document.getElementById("weather-form");

  beforeEach(() => {
    jest.clearAllMocks();
    cityInput.value = "";
    resultContainer.innerHTML = "";
    errorContainer.innerHTML = "";
  });

  it("should show error if city name is empty", () => {
    form.dispatchEvent(new Event("submit"));
    expect(errorContainer.innerHTML).toContain("City name cannot be empty.");
  });

  it("should fetch and display weather data", async () => {
    cityInput.value = "Test City";
    fetchWeatherData.mockResolvedValue({ name: "Test City", main: { temp: 25, temp_min: 20, temp_max: 30 } });
    parseWeatherData.mockReturnValue({ city: "Test City", temp: 25, temp_min: 20, temp_max: 30 });

    await form.dispatchEvent(new Event("submit"));

    expect(resultContainer.innerHTML).toContain("Test City");
    expect(resultContainer.innerHTML).toContain("Temperature: 25");
  });

  it("should show error if API fails", async () => {
    cityInput.value = "Test City";
    fetchWeatherData.mockRejectedValue(new Error("API error"));

    await form.dispatchEvent(new Event("submit"));

    expect(errorContainer.innerHTML).toContain("API error");
  });
});