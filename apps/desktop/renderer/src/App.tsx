import { useHealth } from "./hooks/useHealth";
import { useTopics, useTrends, type TrendBrief } from "./hooks/useTrends";
import Review from "./components/Review";
import Episodes from "./components/Episodes";
import {
  useSources,
  useTranscript,
  type SourceBrief,
} from "./hooks/useSources";

function TrendList({ items, testId }: { items: TrendBrief[]; testId: string }) {
  if (items.length === 0) return <p>No data yet — run discovery.</p>;
  return (
    <ul>
      {items.map((t) => (
        <li key={t.id}>
          {t.title} — {t.view_count.toLocaleString()} views (score {t.trend_score})
        </li>
      ))}
    </ul>
  );
}

function SourceRow({ source }: { source: SourceBrief }) {
  const transcript = useTranscript(source.id);
  return (
    <li>
      {source.title || source.external_id} ({source.status})
      <div data-testid={`transcript-${source.id}`}>
        {transcript.loading ? (
          <p>Loading transcript…</p>
        ) : transcript.data ? (
          <p>
            [{transcript.data.segments.length} segments,{" "}
            {transcript.data.language}]{" "}
            {transcript.data.text.slice(0, 200)}
          </p>
        ) : (
          <p>No transcript yet.</p>
        )}
      </div>
    </li>
  );
}
export default function App() {
  const health = useHealth();
  const trends = useTrends();
  const sources = useSources();
  const topics = useTopics();
  return (
    <main style={{ fontFamily: "system-ui", padding: 24 }}>
      <h1>YtPop — Dashboard (S5)</h1>
      <p data-testid="api-status">
        {health.loading ? "API: checking…" : `API: ${health.status}${health.version ? ` (${health.version})` : ""}`}
      </p>
      {health.error && <p data-testid="api-error">{health.error}</p>}
      <section>
        <h2>Trending now</h2>
        <div data-testid="trends-trending">
          {trends.loading ? (
            <p>Loading trends…</p>
          ) : (
            <TrendList items={trends.data?.trending_now ?? []} testId="trends-trending" />
          )}
        </div>
        <h2>Recently rising</h2>
        <div data-testid="trends-rising">
          {!trends.loading && <TrendList items={trends.data?.recently_rising ?? []} testId="trends-rising" />}
        </div>
        <h2>Fastest growing</h2>
        <div data-testid="trends-fastest">
          {!trends.loading && <TrendList items={trends.data?.fastest_growing ?? []} testId="trends-fastest" />}
        </div>
        <h2>Top categories</h2>
        <div data-testid="trends-categories">
          {!trends.loading && (
            <ul>
              {(trends.data?.top_categories ?? []).map((c) => (
                <li key={c.category}>
                  {c.category} ({c.count})
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
      <section>
        <h2>Topics</h2>
        <div data-testid="trends-topics">
          {topics.loading ? (
            <p>Loading topics…</p>
          ) : topics.data.length === 0 ? (
            <p>No topics yet — run trend clustering.</p>
          ) : (
            <ul>
              {topics.data.map((t) => (
                <li key={t.id}>
                  🔥 {t.topic} · {t.sources} videos · +{t.velocity.toLocaleString()}/h ·{" "}
                  {(t.combined_views / 1e6).toFixed(1)}M views · score{" "}
                  {t.score.toFixed(1)}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
      <section>
        <h2>Sources</h2>
        <div data-testid="sources-list">
          {sources.loading ? (
            <p>Loading sources…</p>
          ) : sources.data.length === 0 ? (
            <p>No sources yet — run discovery.</p>
          ) : (
            <ul>
              {sources.data.map((s) => (
                <SourceRow key={s.id} source={s} />
              ))}
            </ul>
          )}
        </div>
      </section>
      <Review />
      <Episodes />
      <nav>
        <ul>
          {["Dashboard", "Trends", "Sources", "Clips", "Episodes", "Review", "Settings"].map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </nav>
    </main>
  );
}
