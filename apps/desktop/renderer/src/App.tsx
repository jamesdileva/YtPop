import { useHealth } from "./hooks/useHealth";

export default function App() {
  const health = useHealth();
  return (
    <main style={{ fontFamily: "system-ui", padding: 24 }}>
      <h1>YtPop — Dashboard (S1)</h1>
      <p data-testid="api-status">
        {health.loading ? "API: checking…" : `API: ${health.status}${health.version ? ` (${health.version})` : ""}`}
      </p>
      {health.error && <p data-testid="api-error">{health.error}</p>}
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
