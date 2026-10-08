import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
  fireEvent,
} from "@testing-library/react";
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
    let reviewed = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, opts?: { method?: string }) => {
        const u = String(url);
        if (u.includes("/api/v1/trends")) {
          return Promise.resolve({ json: () => Promise.resolve(TRENDS_FIXTURE) });
        }
        if (u.includes("/trend-events")) {
          return Promise.resolve({
            json: () =>
              Promise.resolve([
                {
                  id: 1, topic: "Game Update", description: "d",
                  score: 91.2, velocity: 184000, category: "gaming",
                  sources: 12, combined_views: 4200000,
                },
              ]),
          });
        }
        if (u.includes("/moments")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
        }
        if (u.includes("/episodes")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
        }
        if (u.includes("/transcript")) {
          return Promise.resolve({
            ok: true, json: () => Promise.resolve(TRANSCRIPT_FIXTURE),
          });
        }
        if (u.includes("/api/v1/sources")) {
          return Promise.resolve({ json: () => Promise.resolve(SOURCES_FIXTURE) });
        }
        if (u.includes("/api/v1/jobs")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ jobs: [], queue_depth: {} }),
          });
        }
        if (u.includes("/review")) {
          reviewed = true;
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ source_id: 7, status: "REVIEW_REQUIRED" }),
          });
        }
        if (u.includes("/api/v1/rights")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                source_id: 7,
                status: reviewed ? "REVIEW_REQUIRED" : "UNKNOWN",
                basis: "",
              }),
          });
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

  it("renders topic cards from trend clustering", async () => {
    render(<App />);
    await waitFor(() =>
      expect(screen.getByTestId("trends-topics").textContent).toContain("Game Update"),
    );
    expect(screen.getByTestId("trends-topics").textContent).toContain("12 videos");
    expect(screen.getByTestId("trends-topics").textContent).toContain("4.2M views");
  });

  it("shows rights badge with review banner and request flow", async () => {
    render(<App />);
    await waitFor(() =>
      expect(screen.getByTestId("rights-7").textContent).toContain("Rights: UNKNOWN"),
    );
    expect(screen.getByTestId("rights-7").textContent).toContain(
      "Rights basis: human review required.",
    );
    fireEvent.click(screen.getByTestId("request-review-7"));
    await waitFor(() =>
      expect(screen.getByTestId("rights-7").textContent).toContain("REVIEW_REQUIRED"),
    );
  });
});
