import { useState } from "react";
import {
  renderFileUrl,
  useEpisodes,
  type Episode,
  type RenderResult,
} from "../hooks/useEpisodes";
import { useMoments } from "../hooks/useMoments";

function fmt(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function RenderPanel({
  ep,
  render,
}: {
  ep: Episode;
  render: (episodeId: number, preset: string) => Promise<RenderResult>;
}) {
  const [preset, setPreset] = useState("preview_720p");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RenderResult | null>(null);
  const [error, setError] = useState("");

  return (
    <div data-testid={`render-panel-${ep.id}`}>
      <select
        data-testid={`render-preset-${ep.id}`}
        value={preset}
        onChange={(e) => setPreset(e.target.value)}
      >
        {["preview_720p", "youtube_1080p", "vertical_1080x1920"].map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
      <button
        data-testid={`render-btn-${ep.id}`}
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setError("");
          render(ep.id, preset)
            .then(setResult)
            .catch((e: unknown) =>
              setError(e instanceof Error ? e.message : "render failed"),
            )
            .finally(() => setBusy(false));
        }}
      >
        {busy ? "Rendering…" : "Render"}
      </button>
      {error && <p data-testid={`render-error-${ep.id}`}>{error}</p>}
      {result && (
        <div data-testid={`render-result-${ep.id}`}>
          <video
            data-testid={`render-video-${ep.id}`}
            src={renderFileUrl(result.render_id)}
            controls
            preload="none"
            width={480}
          />
          <p data-testid={`render-qa-${ep.id}`}>
            QA {result.qa.ok ? "pass" : "FAIL"} — {result.qa.duration}s,{" "}
            {result.qa.resolution}, {result.qa.fps}fps
          </p>
        </div>
      )}
    </div>
  );
}

function Timeline({
  ep,
  move,
  remove,
  addClip,
  render,
}: {
  ep: Episode;
  move: (ep: Episode, index: number, delta: number) => Promise<Episode>;
  remove: (episodeId: number, segmentId: number) => Promise<Episode>;
  addClip: (episodeId: number, momentId: number) => Promise<Episode>;
  render: (episodeId: number, preset: string) => Promise<RenderResult>;
}) {
  const approved = useMoments("APPROVED");
  const [momentId, setMomentId] = useState("");

  return (
    <div data-testid={`timeline-${ep.id}`}>
      <p data-testid={`duration-${ep.id}`}>
        {fmt(ep.actual_duration)} / {fmt(ep.target_duration)} (
        {ep.over_under >= 0 ? "+" : ""}
        {fmt(Math.abs(ep.over_under))} {ep.over_under >= 0 ? "over" : "under"})
      </p>
      <ol>
        {ep.segments.map((s, i) => (
          <li key={s.id} data-testid={`seg-${s.id}`}>
            [{s.kind}] {s.moment_id ? `clip m${s.moment_id}` : s.context_text} —{" "}
            {s.duration.toFixed(1)}s
            <button data-testid={`up-${s.id}`} onClick={() => void move(ep, i, -1)}>
              ↑
            </button>
            <button data-testid={`down-${s.id}`} onClick={() => void move(ep, i, 1)}>
              ↓
            </button>
            <button data-testid={`del-${s.id}`} onClick={() => void remove(ep.id, s.id)}>
              ✕
            </button>
          </li>
        ))}
      </ol>
      <div>
        <input
          data-testid={`add-moment-${ep.id}`}
          placeholder="approved moment id"
          value={momentId}
          onChange={(e) => setMomentId(e.target.value)}
        />
        <button
          data-testid={`add-btn-${ep.id}`}
          onClick={() => {
            if (momentId) void addClip(ep.id, Number(momentId));
            setMomentId("");
          }}
        >
          Add clip
        </button>
        {!approved.loading && (
          <span data-testid={`approved-count-${ep.id}`}>
            {approved.data.length} approved available
          </span>
        )}
      </div>
      <RenderPanel ep={ep} render={render} />
    </div>
  );
}

export default function Episodes() {
  const { data, loading, refresh, create, move, remove, addClip, render } =
    useEpisodes();
  const [title, setTitle] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);

  return (
    <section>
      <h2>Episodes</h2>
      <div>
        <input
          data-testid="episode-title"
          placeholder="New episode title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <button
          data-testid="episode-create"
          onClick={() => {
            void create(title).then((ep) => {
              setTitle("");
              setOpenId(ep.id);
              void refresh();
            });
          }}
        >
          New episode
        </button>
      </div>
      {loading ? (
        <p>Loading episodes…</p>
      ) : (
        <ul data-testid="episode-list">
          {data.map((ep) => (
            <li key={ep.id}>
              <button data-testid={`episode-${ep.id}`} onClick={() => setOpenId(openId === ep.id ? null : ep.id)}>
                {ep.title} ({ep.segments.length} segs)
              </button>
              {openId === ep.id && (
                <Timeline
                  key={ep.id}
                  ep={ep}
                  move={move}
                  remove={remove}
                  addClip={addClip}
                  render={render}
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
