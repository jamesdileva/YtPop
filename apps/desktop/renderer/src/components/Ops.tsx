import { useState } from "react";
import { useJobs, type PipelineResult } from "../hooks/useJobs";

export default function Ops() {
  const { jobs, depth, loading, refresh, dailyEpisode } = useJobs();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState("");

  const failures = jobs.filter((j) => j.status === "FAILED").length;

  return (
    <section>
      <h2>Operations</h2>
      <div data-testid="ops-depth">
        {loading ? (
          <p>Loading jobs…</p>
        ) : (
          <p>
            queued: {depth.QUEUED ?? 0} · running: {depth.RUNNING ?? 0} ·
            done: {depth.COMPLETED ?? 0} · failed: {failures}
          </p>
        )}
      </div>
      <button
        data-testid="daily-episode-btn"
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
      {error && <p data-testid="ops-error">{error}</p>}
      {result && (
        <div data-testid="ops-result">
          <p data-testid="ops-episode">
            Episode {result.episode_id} from “{result.trend}” — render{" "}
            {result.render_id}
          </p>
          <ul>
            {result.stages.map((s) => (
              <li key={s.stage}>
                {s.stage}: {s.status}
              </li>
            ))}
          </ul>
        </div>
      )}
      <ul data-testid="ops-jobs">
        {jobs.slice(0, 10).map((j) => (
          <li key={j.id}>
            #{j.id} {j.type} [{j.status}] pri {j.priority}
            {j.error ? ` — ${j.error.slice(0, 80)}` : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}
