import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
  fireEvent,
} from "@testing-library/react";
import Review from "./Review";

const MOMENTS = [
  {
    id: 1, source_id: 9, start_time: 5, end_time: 15,
    transcript_excerpt: "How to win?", moment_type: "question",
    semantic_score: 0.8, emotion_score: 12, novelty_score: 0.9,
    editorial_score: 16, final_score: 82.5, status: "CANDIDATE",
    notes: "", category: "", is_best: false,
  },
  {
    id: 2, source_id: 9, start_time: 20, end_time: 30,
    transcript_excerpt: "Boring filler.", moment_type: "highlight",
    semantic_score: 0.1, emotion_score: 1, novelty_score: 0.4,
    editorial_score: 2, final_score: 20.0, status: "CANDIDATE",
    notes: "", category: "", is_best: false,
  },
];

function mockApi(patched: { url: string; body: string }[] = []) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, opts?: { method?: string; body?: string }) => {
      if (opts?.method === "PATCH") {
        patched.push({ url: String(url), body: String(opts.body) });
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ...MOMENTS[0], status: "APPROVED" }),
        });
      }
      return Promise.resolve({ json: () => Promise.resolve(MOMENTS) });
    }),
  );
}

describe("Review queue", () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    mockApi();
  });

  it("lists candidates with scores", async () => {
    render(<Review />);
    await waitFor(() => expect(screen.getByTestId("queue-1")).toBeInTheDocument());
    expect(screen.getByTestId("queue-2")).toBeInTheDocument();
    expect(screen.getByTestId("review-excerpt").textContent).toContain("How to win?");
  });

  it("shows score breakdown bars", async () => {
    render(<Review />);
    await waitFor(() => expect(screen.getByTestId("bar-Score")).toBeInTheDocument());
    for (const label of ["bar-Hook", "bar-Emotion", "bar-Novelty", "bar-Context"]) {
      expect(screen.getByTestId(label)).toBeInTheDocument();
    }
  });

  it("approve sends PATCH with status", async () => {
    const patched: { url: string; body: string }[] = [];
    mockApi(patched);
    render(<Review />);
    await waitFor(() => expect(screen.getByTestId("btn-approve")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("btn-approve"));
    await waitFor(() => expect(patched.length).toBe(1));
    expect(patched[0].url).toContain("/api/v1/moments/1");
    expect(patched[0].body).toContain("APPROVED");
  });

  it("keyboard a approves, j moves selection", async () => {
    const patched: { url: string; body: string }[] = [];
    mockApi(patched);
    render(<Review />);
    await waitFor(() => expect(screen.getByTestId("review-card")).toBeInTheDocument());
    fireEvent.keyDown(window, { key: "j" });
    await waitFor(() =>
      expect(screen.getByTestId("review-excerpt").textContent).toContain("Boring filler."),
    );
    fireEvent.keyDown(window, { key: "a" });
    await waitFor(() => expect(patched.length).toBe(1));
    expect(patched[0].url).toContain("/api/v1/moments/2");
  });

  it("video previews the selected moment", async () => {
    render(<Review />);
    await waitFor(() => expect(screen.getByTestId("review-video")).toBeInTheDocument());
    const src = (screen.getByTestId("review-video") as HTMLVideoElement).src;
    expect(src).toContain("/api/v1/moments/1/preview");
  });
});
