import { useEffect, useState } from "react";

export type TrendBrief = {
  id: number;
  external_id: string;
  title: string;
  channel_name: string;
  category: string;
  view_count: number;
  trend_score: number;
  velocity_per_hour: number;
};

export type TopCategory = { category: string; count: number };

export type TrendsData = {
  trending_now: TrendBrief[];
  recently_rising: TrendBrief[];
  fastest_growing: TrendBrief[];
  top_categories: TopCategory[];
};

const DEFAULT_URL =
  (import.meta as unknown as { env?: Record<string, string> }).env
    ?.VITE_API_URL ?? "http://127.0.0.1:8000";

export function getTrendsUrl(base: string = DEFAULT_URL): string {
  return `${base.replace(/\/$/, "")}/api/v1/trends`;
}

export function useTrends(base?: string): {
  data: TrendsData | null;
  loading: boolean;
  error?: string;
} {
  const [data, setData] = useState<TrendsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    fetch(getTrendsUrl(base))
      .then((r) => r.json())
      .then((body: TrendsData) => {
        if (alive) {
          setData(body);
          setLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (alive) {
          setError(e instanceof Error ? e.message : "fetch failed");
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
  }, [base]);

  return { data, loading, error };
}

export type TopicCard = {
  id: number;
  topic: string;
  description: string;
  score: number;
  velocity: number;
  category: string;
  sources: number;
  combined_views: number;
};

export function useTopics(base?: string): {
  data: TopicCard[];
  loading: boolean;
} {
  const [data, setData] = useState<TopicCard[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const root = getTrendsUrl(base).replace(/\/trends$/, "");
    fetch(`${root}/trend-events`)
      .then((r) => r.json())
      .then((body: TopicCard[]) => {
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
  }, [base]);

  return { data, loading };
}
