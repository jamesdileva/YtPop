import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
  fireEvent,
} from "@testing-library/react";
import Ops from "./Ops";

function mockApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const u = String(url);
      if (u.includes("/pipeline/daily-episode")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              episode_id: 9,
              render_id: 4,
              trend: "Game Update",
              stages: [
                { stage: "cluster", status: "COMPLETED", detail: "ok" },
                { stage: "render", status: "COMPLETED", detail: "ok" },
              ],
              publishable: false,
              review: "review it",
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            jobs: [
              { id: 1, type: "CLUSTER", status: "COMPLETED", priority: 30, payload: "{}", progress: 1, attempts: 1, error: "" },
              { id: 2, type: "RENDER", status: "FAILED", priority: 30, payload: "{}", progress: 0, attempts: 2, error: "boom" },
            ],
            queue_depth: { COMPLETED: 1, FAILED: 1 },
          }),
      });
    }),
  );
}

describe("Ops", () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    mockApi();
  });

  it("shows queue depth and failures", async () => {
    render(<Ops />);
    await waitFor(() => expect(screen.getByTestId("ops-depth").textContent).toContain("failed: 1"));
    expect(screen.getByTestId("ops-jobs").textContent).toContain("CLUSTER");
    expect(screen.getByTestId("ops-jobs").textContent).toContain("boom");
  });

  it("daily-episode button shows episode and stages", async () => {
    render(<Ops />);
    await waitFor(() => expect(screen.getByTestId("daily-episode-btn")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("daily-episode-btn"));
    await waitFor(() =>
      expect(screen.getByTestId("ops-episode").textContent).toContain("Episode 9"),
    );
    expect(screen.getByTestId("ops-result").textContent).toContain("cluster: COMPLETED");
  });
});
