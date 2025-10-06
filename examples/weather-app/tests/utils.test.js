/**
 * Tests for utils.js - Weather App utility methods
 */

import { fetchWeatherData, parseWeatherData } from "../js/utils.js";

describe("fetchWeatherData", () => {
  it("should fetch weather data successfully when API responds with valid data", async () => {
    const mockUrl = "https://api.mockweather.com/data/test";
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ name: "Test City", main: { temp: 25, temp_min: 20, temp_max: 30 } }),
      })
    );

    const data = await fetchWeatherData(mockUrl);
    expect(data.name).toBe("Test City");
    expect(data.main.temp).toBe(25);
  });

  it("should throw an error when API responds with a failure status", async () => {
    const mockUrl = "https://api.mockweather.com/data/test";
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        status: 404,
      })
    );

    await expect(fetchWeatherData(mockUrl)).rejects.toThrow("HTTP error! Status: 404");
  });

  it("should throw an error when fetch fails completely", async () => {
    const mockUrl = "https://api.mockweather.com/data/test";
    global.fetch = jest.fn(() => Promise.reject(new Error("Network Error")));

    await expect(fetchWeatherData(mockUrl)).rejects.toThrow("Network Error");
  });
});

describe("parseWeatherData", () => {
  it("should parse valid weather data correctly", () => {
    const mockData = { name: "Test City", main: { temp: 25, temp_min: 20, temp_max: 30 } };
    const result = parseWeatherData(mockData);

    expect(result.city).toBe("Test City");
    expect(result.temp).toBe(25);
    expect(result.temp_min).toBe(20);
    expect(result.temp_max).toBe(30);
  });

  it("should throw an error for invalid weather data", () => {
    const mockData = null;
    expect(() => parseWeatherData(mockData)).toThrow("Invalid weather data: Data is undefined or not an object");
  });

  it("should throw an error for missing fields in weather data", () => {
    const mockData = { name: "Test City" };
    expect(() => parseWeatherData(mockData)).toThrow("Incomplete weather data: Missing expected fields");
  });
});