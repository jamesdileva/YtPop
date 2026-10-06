import { useEffect, useState } from "react";

export type SourceBrief = {
  id: number;
  external_id: string;
  title: string;
  channel_name: string;
  status: string;
};

export type TranscriptSegment = {
  start: number;
  end: number;
  text: string;
  words: { start: number; end: number; word: string }[];
};

export type TranscriptData = {
  id: number;
  language: string;
  model: string;
  text: string;
  segments: TranscriptSegment[];
};

const DEFAULT_URL =
  (import.meta as unknown as { env?: Record<string, string> }).env
    ?.VITE_API_URL ?? "http://127.0.0.1:8000";

export function apiUrl(path: string, base: string = DEFAULT_URL): string {
  return `${base.replace(/\/$/, "")}${path}`;
}

export function useSources(base?: string): {
  data: SourceBrief[];
  loading: boolean;
} {
  const [data, setData] = useState<SourceBrief[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fetch(apiUrl("/api/v1/sources", base))
      .then((r) => r.json())
      .then((body: SourceBrief[]) => {
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

export function useTranscript(
  sourceId: number | null,
  base?: string,
): { data: TranscriptData | null; loading: boolean } {
  const [data, setData] = useState<TranscriptData | null>(null);
  const [loading, setLoading] = useState(sourceId !== null);

  useEffect(() => {
    if (sourceId === null) return;
    let alive = true;
    setLoading(true);
    fetch(apiUrl(`/api/v1/sources/${sourceId}/transcript`, base))
      .then((r) => {
        if (!r.ok) throw new Error("no transcript");
        return r.json();
      })
      .then((body: TranscriptData) => {
        if (alive) {
          setData(body);
          setLoading(false);
        }
      })
      .catch(() => {
        if (alive) {
          setData(null);
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
  }, [sourceId, base]);

  return { data, loading };
}
