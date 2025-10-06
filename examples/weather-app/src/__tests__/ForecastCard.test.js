import React from "react";
import { render, screen } from "@testing-library/react";
import ForecastCard from "../components/ForecastCard";

describe("ForecastCard Component", () => {
  const mockProps = {
    day: "Monday",
    date: "2023-10-23",
    temperature: 25,
    weatherDescription: "Sunny",
    icon: "https://example.com/sunny-icon.png",
  };

  test("renders all provided props correctly", () => {
    render(<ForecastCard {...mockProps} />);

    // Assert day of the week
    const dayElement = screen.getByText("Monday");
    expect(dayElement).toBeInTheDocument();

    // Assert date
    const dateElement = screen.getByText("2023-10-23");
    expect(dateElement).toBeInTheDocument();

    // Assert temperature
    const temperatureElement = screen.getByText("25°C");
    expect(temperatureElement).toBeInTheDocument();

    // Assert description
    const descriptionElement = screen.getByText("Sunny");
    expect(descriptionElement).toBeInTheDocument();

    // Assert icon
    const iconElement = screen.getByAltText("Sunny");
    expect(iconElement).toBeInTheDocument();
    expect(iconElement).toHaveAttribute("src", "https://example.com/sunny-icon.png");
  });

  test("renders correct HTML structure", () => {
    const { container } = render(<ForecastCard {...mockProps} />);
    expect(container.querySelector(".forecast-card")).toBeInTheDocument();
    expect(container.querySelector(".forecast-card-day")).toHaveTextContent("Monday");
    expect(container.querySelector(".forecast-card-temperature")).toHaveTextContent("25°C");
  });
});