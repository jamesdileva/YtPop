import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import App from "./App";
import { getHealthUrl } from "./hooks/useHealth";
import { getTrendsUrl } from "./hooks/useTrends";

const SOURCES_FIXTURE = [
  { id: 7, external_id: "vid1", title: "Vid 1", channel_name: "Ch", status: "DISCOVERED" },
];

const TRANSCRIPT_FIXTURE = {
  id: 3, language: "en", model: "tiny", text: "Hello world.",
  segments: [{ start: 0, end: 1.1, text: "Hello world.", words: [] }],
};

const TRENDS_FIXTURE = {
  trending_now: [
    {
      id: 1, external_id: "vid1", title: "Vid 1", channel_name: "Ch",
      category: "gaming", view_count: 5000, trend_score: 40.1, velocity_per_hour: 0,
    },
  ],
  recently_rising: [],
  fastest_growing: [
    {
      id: 1, external_id: "vid1", title: "Vid 1", channel_name: "Ch",
      category: "gaming", view_count: 5000, trend_score: 40.1, velocity_per_hour: 0,
    },
  ],
  top_categories: [{ category: "gaming", count: 1 }],
};

describe("getHealthUrl", () => {
  it("builds /api/v1/health URL", () => {
    expect(getHealthUrl("http://127.0.0.1:8000")).toBe("http://127.0.0.1:8000/api/v1/health");
  });
});

describe("getTrendsUrl", () => {
  it("builds /api/v1/trends URL", () => {
    expect(getTrendsUrl("http://127.0.0.1:8000")).toBe("http://127.0.0.1:8000/api/v1/trends");
  });
});

describe("App health badge + trends sections", () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const u = String(url);
        if (u.includes("/api/v1/trends")) {
          return Promise.resolve({ json: () => Promise.resolve(TRENDS_FIXTURE) });
        }
        if (u.includes("/transcript")) {
          return Promise.resolve({
            ok: true, json: () => Promise.resolve(TRANSCRIPT_FIXTURE),
          });
        }
        if (u.includes("/api/v1/sources")) {
          return Promise.resolve({ json: () => Promise.resolve(SOURCES_FIXTURE) });
        }
        return Promise.resolve({ json: () => Promise.resolve({ status: "ok", version: "0.1.0" }) });
      }),
    );
  });

  it("shows API: ok after fetch", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("api-status").textContent).toContain("API: ok"));
  });

  it("renders all four discovery sections", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("trends-trending").textContent).toContain("Vid 1"));
    expect(screen.getByTestId("trends-rising")).toBeInTheDocument();
    expect(screen.getByTestId("trends-fastest").textContent).toContain("Vid 1");
    expect(screen.getByTestId("trends-categories").textContent).toContain("gaming");
  });

  it("lists sources with transcript timeline", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("sources-list").textContent).toContain("Vid 1"));
    await waitFor(() => expect(screen.getByTestId("transcript-7").textContent).toContain("Hello world."));
    expect(screen.getByTestId("transcript-7").textContent).toContain("1 segments");
  });
});
