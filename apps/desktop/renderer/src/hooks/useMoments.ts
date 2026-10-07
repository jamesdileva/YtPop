import { useCallback, useEffect, useState } from "react";
import { apiUrl } from "./useSources";

export type Moment = {
  id: number;
  source_id: number;
  start_time: number;
  end_time: number;
  transcript_excerpt: string;
  moment_type: string;
  semantic_score: number;
  emotion_score: number;
  novelty_score: number;
  editorial_score: number;
  final_score: number;
  status: string;
  notes: string;
  category: string;
  is_best: boolean;
};

export type ReviewPatch = {
  status?: string;
  start_time?: number;
  end_time?: number;
  notes?: string;
  category?: string;
  is_best?: boolean;
  reason?: string;
};

export function previewUrl(id: number, base?: string): string {
  return apiUrl(`/api/v1/moments/${id}/preview`, base);
}

export function useMoments(statusFilter: string = "ALL", base?: string): {
  data: Moment[];
  loading: boolean;
  refresh: () => void;
} {
  const [data, setData] = useState<Moment[]>([]);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    const q =
      statusFilter === "ALL" ? "" : `?status=${statusFilter}&limit=100`;
    fetch(apiUrl(`/api/v1/moments${q || "?limit=100"}`, base))
      .then((r) => r.json())
      .then((body: Moment[]) => {
        if (alive) {
          setData(body);
          setLoading(false);
        }
      })
      .catch(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [statusFilter, nonce, base]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);
  return { data, loading, refresh };
}

export async function patchMoment(
  id: number,
  body: ReviewPatch,
  base?: string,
): Promise<Moment> {
  const r = await fetch(apiUrl(`/api/v1/moments/${id}`, base), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`review failed: ${r.status}`);
  return r.json() as Promise<Moment>;
}
