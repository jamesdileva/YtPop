import { useCallback, useEffect, useState } from "react";
import { apiUrl } from "./useSources";

export type Job = {
  id: number;
  type: string;
  status: string;
  priority: number;
  payload: string;
  progress: number;
  attempts: number;
  error: string;
};

export type PipelineResult = {
  episode_id: number;
  render_id: number;
  trend: string;
  stages: { stage: string; status: string; detail: string }[];
  publishable: boolean;
  review: string;
};

async function req<T>(path: string, init?: RequestInit, base?: string): Promise<T> {
  const r = await fetch(apiUrl(path, base), {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!r.ok) throw new Error(`jobs api failed: ${r.status}`);
  return r.json() as Promise<T>;
}

export function useJobs(base?: string) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [depth, setDepth] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const body = await req<{ jobs: Job[]; queue_depth: Record<string, number> }>(
        "/api/v1/jobs?limit=50",
        undefined,
        base,
      );
      setJobs(body.jobs);
      setDepth(body.queue_depth);
    } finally {
      setLoading(false);
    }
  }, [base]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const dailyEpisode = useCallback(
    () =>
      req<PipelineResult>(
        "/api/v1/pipeline/daily-episode",
        { method: "POST", body: JSON.stringify({}) },
        base,
      ),
    [base],
  );

  return { jobs, depth, loading, refresh, dailyEpisode };
}
