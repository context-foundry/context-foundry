import { describe, test, expect } from "vitest";
import { getState, updateState, subscribe } from "../state/store";

describe("Global State Management Tests", () => {
  test("Should get the default state", () => {
    const state = getState();
    expect(state.city).toBe("London");
    expect(state.weatherData).toBeNull();
  });

  test("Should update the state", () => {
    updateState({ city: "New York" });
    const state = getState();
    expect(state.city).toBe("New York");
  });

  test("Subscribers should be notified on state changes", () => {
    const mockCallback = vi.fn();
    const unsubscribe = subscribe(mockCallback);

    updateState({ city: "Tokyo" });
    expect(mockCallback).toHaveBeenCalledWith({ city: "Tokyo", weatherData: null });

    unsubscribe();
    updateState({ city: "Paris" });
    expect(mockCallback).not.toHaveBeenCalledWith({ city: "Paris", weatherData: null });
  });
});