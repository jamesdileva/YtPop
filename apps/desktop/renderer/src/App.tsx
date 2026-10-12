import { useHealth } from "./hooks/useHealth";
import { useTopics, useTrends, type TrendBrief } from "./hooks/useTrends";
import Review from "./components/Review";
import Episodes from "./components/Episodes";
import Ops from "./components/Ops";
import {
  isRightsApproved,
  requestReview,
  useRights,
  useSources,
  useTranscript,
  type SourceBrief,
} from "./hooks/useSources";

function TrendList({ items }: { items: TrendBrief[] }) {
  if (items.length === 0) return <p className="empty">No data yet — run discovery.</p>;
  return (
    <ul className="list">
      {items.map((t) => (
        <li key={t.id}>
          <span>{t.title}</span>
          <span className="muted">
            {t.view_count.toLocaleString()} views · score {t.trend_score}
          </span>
        </li>
      ))}
    </ul>
  );
}

function RightsBadge({ sourceId }: { sourceId: number }) {
  const rights = useRights(sourceId);
  if (rights.loading || !rights.data) return null;
  const approved = isRightsApproved(rights.data.status);
  return (
    <span data-testid={`rights-${sourceId}`}>
      Rights: {rights.data.status}
      {!approved && " — Rights basis: human review required."}
      {!approved && (
        <button
          data-testid={`request-review-${sourceId}`}
          onClick={() => {
            void requestReview(sourceId).then(() => rights.refresh());
          }}
        >
          Request review
        </button>
      )}
    </span>
  );
}

function SourceRow({ source }: { source: SourceBrief }) {
  const transcript = useTranscript(source.id);
  return (
    <li>
      <span>
        {source.title || source.external_id}
        <span className="badge">{source.status}</span>
      </span>
      <RightsBadge sourceId={source.id} />
      <div data-testid={`transcript-${source.id}`} className="muted">
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

const NAV = ["Dashboard", "Trends", "Sources", "Clips", "Episodes", "Review", "Settings"];

export default function App() {
  const health = useHealth();
  const trends = useTrends();
  const sources = useSources();
  const topics = useTopics();
  const healthState = health.loading
    ? "checking"
    : health.status === "ok"
      ? "ok"
      : "down";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          Yt<span>Pop</span>
        </div>
        <nav>
          {NAV.map((item) => (
            <div
              key={item}
              className={`nav-item${item === "Dashboard" ? " active" : ""}${
                item === "Dashboard" || item === "Review" || item === "Episodes"
                  ? ""
                  : " coming-soon"
              }`}
            >
              {item}
            </div>
          ))}
        </nav>
      </aside>
      <div className="main">
        <header className="page-header">
          <h1>Dashboard</h1>
          <span className="health-pill" data-status={healthState}>
            <span className="health-dot" />
            <span data-testid="api-status">
              {health.loading
                ? "API: checking…"
                : `API: ${health.status}${health.version ? ` (${health.version})` : ""}`}
            </span>
          </span>
        </header>
        {health.error && <p data-testid="api-error">{health.error}</p>}
        <div className="card-grid">
          <section className="card">
            <h2>Trending now</h2>
            <div data-testid="trends-trending">
              {trends.loading ? (
                <p>Loading trends…</p>
              ) : (
                <TrendList items={trends.data?.trending_now ?? []} />
              )}
            </div>
          </section>
          <section className="card">
            <h2>Recently rising</h2>
            <div data-testid="trends-rising">
              {!trends.loading && (
                <TrendList items={trends.data?.recently_rising ?? []} />
              )}
            </div>
          </section>
          <section className="card">
            <h2>Fastest growing</h2>
            <div data-testid="trends-fastest">
              {!trends.loading && (
                <TrendList items={trends.data?.fastest_growing ?? []} />
              )}
            </div>
          </section>
          <section className="card">
            <h2>Top categories</h2>
            <div data-testid="trends-categories">
              {!trends.loading && (
                <ul className="list">
                  {(trends.data?.top_categories ?? []).map((c) => (
                    <li key={c.category}>
                      <span>{c.category}</span>
                      <span className="muted">{c.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>
        <section className="card">
          <h2>Topics</h2>
          <div data-testid="trends-topics">
            {topics.loading ? (
              <p>Loading topics…</p>
            ) : topics.data.length === 0 ? (
              <p className="empty">No topics yet — run trend clustering.</p>
            ) : (
              <ul className="list">
                {topics.data.map((t) => (
                  <li key={t.id} className="topic">
                    <span className="topic-score">{t.score.toFixed(1)}</span>
                    <span className="topic-body">
                      <div className="topic-title">🔥 {t.topic}</div>
                      <div className="topic-meta">
                        {t.sources} videos · +{t.velocity.toLocaleString()}/h ·{" "}
                        {(t.combined_views / 1e6).toFixed(1)}M views
                      </div>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
        <section className="card">
          <h2>Sources</h2>
          <div data-testid="sources-list">
            {sources.loading ? (
              <p>Loading sources…</p>
            ) : sources.data.length === 0 ? (
              <p className="empty">No sources yet — run discovery.</p>
            ) : (
              <ul className="list">
                {sources.data.map((s) => (
                  <SourceRow key={s.id} source={s} />
                ))}
              </ul>
            )}
          </div>
        </section>
        {NAV.some((n) => n === "Dashboard" || n === "Review" || n === "Episodes") && (
          <>
            <Review />
            <Episodes />
            <Ops />
          </>
        )}
      </div>
    </div>
  );
}
