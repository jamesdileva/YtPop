import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
  fireEvent,
} from "@testing-library/react";
import Episodes from "./Episodes";

let EPISODES = [
  {
    id: 1, title: "Ep 1", format: "daily_highlights", theme: "",
    target_duration: 1200, actual_duration: 17, over_under: -1183,
    status: "DRAFT",
    segments: [
      { id: 10, moment_id: null, sequence: 0, duration: 4, transition_type: "cut", commentary_text: "", context_text: "intro", kind: "card" },
      { id: 11, moment_id: 5, sequence: 1, duration: 8, transition_type: "cut", commentary_text: "", context_text: "", kind: "clip" },
      { id: 12, moment_id: null, sequence: 2, duration: 5, transition_type: "cut", commentary_text: "", context_text: "outro", kind: "card" },
    ],
  },
];

function mockApi(calls: string[] = []) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, opts?: { method?: string; body?: string }) => {
      const u = String(url);
      calls.push(`${opts?.method || "GET"} ${u}`);
      if (u.includes("/api/v1/moments")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      }
      if (u.includes("/render")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              render_id: 3,
              path: "/data/renders/3.mp4",
              preset: "preview_720p",
              qa: {
                ok: true, failed: [], duration: 17,
                resolution: "1280x720", fps: 30,
              },
            }),
        });
      }
      if (u.includes("/api/v1/episodes") && (opts?.method === "POST" || opts?.method === "PATCH" || opts?.method === "DELETE")) {
        // echo the stored episode (simulate server echo with reorder applied for rebuild)
        const ep = { ...EPISODES[0] };
        if (u.includes("/rebuild") && opts?.body) {
          const ids = JSON.parse(String(opts.body)).segment_ids as number[];
          ep.segments = ids.map((id) => ep.segments.find((s) => s.id === id)!);
        }
        EPISODES = [ep];
        return Promise.resolve({ ok: true, json: () => Promise.resolve(ep) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(EPISODES) });
    }),
  );
}

describe("Episodes timeline", () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    mockApi();
  });

  it("lists episodes with over/under duration", async () => {
    render(<Episodes />);
    await waitFor(() => expect(screen.getByTestId("episode-1")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("episode-1"));
    await waitFor(() => expect(screen.getByTestId("timeline-1")).toBeInTheDocument());
    expect(screen.getByTestId("duration-1").textContent).toContain("under");
  });

  it("move sends rebuild with swapped order", async () => {
    const calls: string[] = [];
    mockApi(calls);
    render(<Episodes />);
    await waitFor(() => expect(screen.getByTestId("episode-1")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("episode-1"));
    await waitFor(() => expect(screen.getByTestId("down-11")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("down-11"));
    await waitFor(() =>
      expect(calls.some((c) => c.startsWith("POST") && c.includes("/rebuild"))).toBe(true),
    );
  });

  it("delete removes the segment", async () => {
    const calls: string[] = [];
    mockApi(calls);
    render(<Episodes />);
    await waitFor(() => expect(screen.getByTestId("episode-1")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("episode-1"));
    await waitFor(() => expect(screen.getByTestId("del-11")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("del-11"));
    await waitFor(() =>
      expect(calls.some((c) => c.startsWith("DELETE") && c.includes("/segments/11"))).toBe(true),
    );
  });

  it("render shows player with QA summary", async () => {
    render(<Episodes />);
    await waitFor(() => expect(screen.getByTestId("episode-1")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("episode-1"));
    await waitFor(() => expect(screen.getByTestId("render-btn-1")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("render-btn-1"));
    await waitFor(() =>
      expect(screen.getByTestId("render-video-1")).toBeInTheDocument(),
    );
    const src = (screen.getByTestId("render-video-1") as HTMLVideoElement).src;
    expect(src).toContain("/api/v1/renders/3/file");
    expect(screen.getByTestId("render-qa-1").textContent).toContain("QA pass");
    expect(screen.getByTestId("render-qa-1").textContent).toContain("1280x720");
  });

  it("failed render surfaces the error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (String(url).includes("/render")) {
          return Promise.resolve({ ok: false, status: 400 });
        }
        if (String(url).includes("/moments")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve(EPISODES) });
      }),
    );
    render(<Episodes />);
    await waitFor(() => expect(screen.getByTestId("episode-1")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("episode-1"));
    await waitFor(() => expect(screen.getByTestId("render-btn-1")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("render-btn-1"));
    await waitFor(() =>
      expect(screen.getByTestId("render-error-1")).toBeInTheDocument(),
    );
  });
});
