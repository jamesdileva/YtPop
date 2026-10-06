import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { getHealthUrl } from "./hooks/useHealth";

describe("getHealthUrl", () => {
  it("builds /api/v1/health URL", () => {
    expect(getHealthUrl("http://127.0.0.1:8000")).toBe("http://127.0.0.1:8000/api/v1/health");
  });
});

describe("App health badge", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        json: () => Promise.resolve({ status: "ok", version: "0.1.0" }),
      }),
    );
  });

  it("shows API: ok after fetch", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("api-status").textContent).toContain("API: ok"));
  });
});
