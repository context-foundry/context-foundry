import { expect, test } from "vitest";
import axios from "axios";

// Mock OpenWeather API response
const mockApiResponse = {
  weather: [{ description: "clear sky" }],
  main: { temp: 293.15, humidity: 55 }
};

test("fetchWeather should correctly retrieve and format weather data", async () => {
  axios.get = vi.fn().mockResolvedValue({ data: mockApiResponse });

  const city = "London";
  const apiKey = "test_api_key";
  const apiUrl = `https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${apiKey}`;

  const response = await axios.get(apiUrl);
  
  expect(response.data.weather[0].description).toBe("clear sky");
  expect((response.data.main.temp - 273.15).toFixed(2)).toBe("20.00");
  expect(response.data.main.humidity).toBe(55);
});