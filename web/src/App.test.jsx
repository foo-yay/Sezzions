import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  it("shows the Sezzions web heading", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /sezzions web control tower/i })
    ).toBeInTheDocument();
  });
});