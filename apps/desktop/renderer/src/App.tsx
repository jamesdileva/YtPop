import { useHealth } from "./hooks/useHealth";
import { useTrends, type TrendBrief } from "./hooks/useTrends";

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

export default function App() {
  const health = useHealth();
  const trends = useTrends();
  return (
    <main style={{ fontFamily: "system-ui", padding: 24 }}>
      <h1>YtPop — Dashboard (S3)</h1>
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
