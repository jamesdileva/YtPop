import { useEffect, useState } from "react";

export type HealthState = {
  status: string;
  version?: string;
  error?: string;
  loading: boolean;
};

/**
 * API base resolution order: preload-injected runtime value (packaged/e2e),
 * build-time VITE_API_URL (plain browser dev), then the localhost default.
 */
function resolveApiBase(): string {
  const injected = (globalThis as unknown as {
    ytpop?: { apiUrl?: string };
  }).ytpop?.apiUrl;
  if (injected) return injected;
  const built = (import.meta as unknown as { env?: Record<string, string> })
    .env?.VITE_API_URL;
  return built ?? "http://127.0.0.1:8000";
}

const DEFAULT_URL = resolveApiBase();

export function getHealthUrl(base: string = DEFAULT_URL): string {
  return `${base.replace(/\/$/, "")}/api/v1/health`;
}

export function useHealth(base?: string): HealthState {
  const [state, setState] = useState<HealthState>({
    status: "unknown",
    loading: true,
  });

  useEffect(() => {
    let alive = true;
    let attempt = 0;
    const maxAttempts = 20; // ~30s: covers a cold backend start

    const poll = () => {
      fetch(getHealthUrl(base))
        .then((r) => r.json())
        .then((body) => {
          if (alive) {
            setState({ status: body.status ?? "unknown",
                       version: body.version, loading: false });
          }
        })
        .catch((e: unknown) => {
          if (!alive) return;
          if (attempt < maxAttempts) {
            attempt += 1;
            setTimeout(poll, 1500);
            return;
          }
          setState({
            status: "down",
            error: e instanceof Error ? e.message : "fetch failed",
            loading: false,
          });
        });
    };
    poll();

    return () => {
      alive = false;
    };
  }, [base]);

  return state;
}
