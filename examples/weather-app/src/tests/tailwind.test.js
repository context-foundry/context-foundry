import { render } from "@testing-library/html";
import { describe, expect, test } from "vitest";

/**
 * Test utility to validate TailwindCSS classes.
 */
describe("TailwindCSS Integration Tests", () => {
  test("Should apply TailwindCSS classes", () => {
    const { container } = render(`
      <div class="bg-gray-100 text-primary p-6 rounded">
        <h1 class="text-3xl font-bold">Testing Tailwind</h1>
        <p class="text-gray-700">Text using TailwindCSS classes.</p>
      </div>
    `);

    const div = container.querySelector("div");
    const h1 = container.querySelector("h1");
    const p = container.querySelector("p");

    expect(div).toHaveClass("bg-gray-100", "text-primary", "p-6", "rounded");
    expect(h1).toHaveClass("text-3xl", "font-bold");
    expect(p).toHaveClass("text-gray-700");
  });
});