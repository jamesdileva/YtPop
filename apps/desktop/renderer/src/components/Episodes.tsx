import { useState } from "react";
import { useEpisodes, type Episode } from "../hooks/useEpisodes";
import { useMoments } from "../hooks/useMoments";

function fmt(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function Timeline({
  ep,
  move,
  remove,
  addClip,
}: {
  ep: Episode;
  move: (ep: Episode, index: number, delta: number) => Promise<Episode>;
  remove: (episodeId: number, segmentId: number) => Promise<Episode>;
  addClip: (episodeId: number, momentId: number) => Promise<Episode>;
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
    </div>
  );
}

export default function Episodes() {
  const { data, loading, refresh, create, move, remove, addClip } = useEpisodes();
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
                <Timeline key={ep.id} ep={ep} move={move} remove={remove} addClip={addClip} />
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
