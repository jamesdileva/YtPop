import { useState } from "react";
import { useJobs, type PipelineResult } from "../hooks/useJobs";

export default function Ops() {
  const { jobs, depth, loading, refresh, dailyEpisode } = useJobs();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState("");

  const failures = jobs.filter((j) => j.status === "FAILED").length;

  return (
    <section className="card">
      <h2>Operations</h2>
      <div data-testid="ops-depth">
        {loading ? (
          <p>Loading jobs…</p>
        ) : (
          <div className="stat-row">
            <div className="stat">
              <span className="stat-value">{depth.QUEUED ?? 0}</span>
              <span className="stat-label">queued</span>
            </div>
            <div className="stat">
              <span className="stat-value">{depth.RUNNING ?? 0}</span>
              <span className="stat-label">running</span>
            </div>
            <div className="stat">
              <span className="stat-value">{depth.COMPLETED ?? 0}</span>
              <span className="stat-label">done</span>
            </div>
            <div className="stat">
              <span className="stat-value">{failures}</span>
              <span className="stat-label">failed</span>
            </div>
          </div>
        )}
      </div>
      <div className="actions">
        <button
          data-testid="daily-episode-btn"
          className="primary"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            setError("");
            dailyEpisode()
              .then((out) => {
                setResult(out);
                void refresh();
              })
              .catch((e: unknown) =>
                setError(e instanceof Error ? e.message : "pipeline failed"),
              )
              .finally(() => setBusy(false));
          }}
        >
          {busy ? "Generating…" : "Generate today's episode"}
        </button>
      </div>
      {error && <p data-testid="ops-error">{error}</p>}
      {result && (
        <div data-testid="ops-result">
          <p data-testid="ops-episode">
            Episode {result.episode_id} from “{result.trend}” — render{" "}
            {result.render_id}
          </p>
          <ul className="list">
            {result.stages.map((s) => (
              <li key={s.stage}>
                <span>{s.stage}</span>
                <span className="badge">{s.status}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <ul data-testid="ops-jobs" className="list">
        {jobs.slice(0, 10).map((j) => (
          <li key={j.id}>
            <span>
              #{j.id} {j.type}{" "}
              <span className="muted">pri {j.priority}</span>
              {j.error ? ` — ${j.error.slice(0, 80)}` : ""}
            </span>
            <span className="badge">{j.status}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
