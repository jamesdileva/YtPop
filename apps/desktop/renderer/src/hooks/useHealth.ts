import { useEffect, useState } from "react";

export type HealthState = {
  status: string;
  version?: string;
  error?: string;
  loading: boolean;
};

const DEFAULT_URL =
  (import.meta as unknown as { env?: Record<string, string> }).env
    ?.VITE_API_URL ?? "http://127.0.0.1:8000";

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
    fetch(getHealthUrl(base))
      .then((r) => r.json())
      .then((body) => {
        if (alive) setState({ status: body.status ?? "unknown", version: body.version, loading: false });
      })
      .catch((e: unknown) => {
        if (alive)
          setState({
            status: "down",
            error: e instanceof Error ? e.message : "fetch failed",
            loading: false,
          });
      });
    return () => {
      alive = false;
    };
  }, [base]);

  return state;
}
