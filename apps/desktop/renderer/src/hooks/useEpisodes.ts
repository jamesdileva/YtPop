import { useCallback, useEffect, useState } from "react";
import { apiUrl } from "./useSources";

export type Segment = {
  id: number;
  moment_id: number | null;
  sequence: number;
  duration: number;
  transition_type: string;
  commentary_text: string;
  context_text: string;
  kind: "clip" | "card";
};

export type Episode = {
  id: number;
  title: string;
  format: string;
  theme: string;
  target_duration: number;
  actual_duration: number;
  over_under: number;
  status: string;
  segments: Segment[];
};

async function req<T>(path: string, init?: RequestInit, base?: string): Promise<T> {
  const r = await fetch(apiUrl(path, base), {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!r.ok) throw new Error(`episodes api failed: ${r.status}`);
  return r.json() as Promise<T>;
}

export function useEpisodes(base?: string) {
  const [data, setData] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setData(await req<Episode[]>("/api/v1/episodes", undefined, base));
    } finally {
      setLoading(false);
    }
  }, [base]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const create = useCallback(
    (title: string) =>
      req<Episode>("/api/v1/episodes", { method: "POST", body: JSON.stringify({ title }) }, base),
    [base],
  );

  const mutate = useCallback(
    async (path: string, init?: RequestInit) => {
      const ep = await req<Episode>(path, init, base);
      setData((prev) => prev.map((e) => (e.id === ep.id ? ep : e)));
      return ep;
    },
    [base],
  );

  const addClip = useCallback(
    (episodeId: number, momentId: number) =>
      mutate(`/api/v1/episodes/${episodeId}/segments`, {
        method: "POST",
        body: JSON.stringify({ moment_id: momentId }),
      }),
    [mutate],
  );

  const move = useCallback(
    (ep: Episode, index: number, delta: number) => {
      const ids = ep.segments.map((s) => s.id);
      const j = index + delta;
      if (index < 0 || j < 0 || j >= ids.length) return Promise.resolve(ep);
      const next = [...ids];
      [next[index], next[j]] = [next[j], next[index]];
      return mutate(`/api/v1/episodes/${ep.id}/rebuild`, {
        method: "POST",
        body: JSON.stringify({ segment_ids: next }),
      });
    },
    [mutate],
  );

  const remove = useCallback(
    (episodeId: number, segmentId: number) =>
      mutate(`/api/v1/episodes/${episodeId}/segments/${segmentId}`, {
        method: "DELETE",
      }),
    [mutate],
  );

  return { data, loading, refresh, create, addClip, move, remove };
}
