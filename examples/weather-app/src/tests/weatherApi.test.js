import { describe, test, vi, expect } from "vitest";
import axios from "axios";
import WeatherApi from "../api/weatherApi";

vi.mock("axios");

describe("WeatherApi Utility Tests", () => {
  const mockApiKey = "test_api_key";
  const api = new WeatherApi(mockApiKey);

  test("Should throw an error if API key is not provided", () => {
    expect(() => new WeatherApi()).toThrow("API key is required to create WeatherApi instance.");
  });

  test("Should fetch current weather data for a city", async () => {
    const mockCity = "London";
    const mockResponse = {
      weather: [{ description: "clear sky" }],
      main: { temp: 293.15, humidity: 55 },
    };

    axios.get.mockResolvedValueOnce({ data: mockResponse });

    const data = await api.fetchCurrentWeather(mockCity);
    expect(data.weather[0].description).toBe("clear sky");
    expect(data.main.temp).toBe(293.15);
    expect(data.main.humidity).toBe(55);

    expect(axios.get).toHaveBeenCalledWith(
      `https://api.openweathermap.org/data/2.5/weather?q=${mockCity}&appid=${mockApiKey}`
    );
  });

  test("Should throw an error when city is not provided to fetchCurrentWeather", async () => {
    await expect(api.fetchCurrentWeather("")).rejects.toThrow("City name is required to fetch weather data.");
  });

  test("Should convert temperature from Kelvin to Celsius", () => {
    const kelvin = 300;
    const celsius = WeatherApi.kelvinToCelsius(kelvin);
    expect(celsius).toBe("26.85");
  });

  test("Should handle errors in fetchCurrentWeather correctly", async () => {
    axios.get.mockRejectedValueOnce(new Error("API request failed"));

    await expect(api.fetchCurrentWeather("Nowhere")).rejects.toThrow("Could not fetch weather data. Please try again.");
  });
});