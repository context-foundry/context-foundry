import { describe, test, expect, vi } from "vitest";
import WeatherCard from "../components/WeatherCard";
import WeatherApi from "../api/weatherApi";

vi.mock("../api/weatherApi");

describe("Core Components Tests", () => {
  test("Header component renders correctly", () => {
    const header = document.createElement("header");
    const child = header.querySelector("h1");
    expect(child).not.toBeNull();
  });

  test("WeatherCard displays city and weather data", async () => {
    const mockApi = {
      fetchCurrentWeather: vi.fn().mockResolvedValue({
        weather: [{ description: "clear sky" }],
        main: { temp: 273.15, humidity: 60 },
      }),
    };