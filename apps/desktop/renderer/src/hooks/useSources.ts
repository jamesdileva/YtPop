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

export function apiUrl(path: string, base: string = DEFAULT_URL): string {
  return `${base.replace(/\/$/, "")}${path}`;
}

export type RightsInfo = {
  id: number | null;
  source_id: number;
  status: string;
  basis: string;
  reviewer: string;
};

const APPROVED_RIGHTS = new Set([
  "APPROVED",
  "PERMISSION_GRANTED",
  "LICENSED",
  "CREATIVE_COMMONS",
  "PUBLIC_DOMAIN",
  "USER_OWNED",
]);

export function isRightsApproved(status: string): boolean {
  return APPROVED_RIGHTS.has(status);
}

export function useRights(
  sourceId: number | null,
  base?: string,
): { data: RightsInfo | null; loading: boolean; refresh: () => void } {
  const [data, setData] = useState<RightsInfo | null>(null);
  const [loading, setLoading] = useState(sourceId !== null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (sourceId === null) return;
    let alive = true;
    setLoading(true);
    fetch(apiUrl(`/api/v1/rights/${sourceId}`, base))
      .then((r) => {
        if (!r.ok) throw new Error("no rights");
        return r.json();
      })
      .then((body: RightsInfo) => {
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
  }, [sourceId, base, nonce]);

  return { data, loading, refresh: () => setNonce((n) => n + 1) };
}

export async function requestReview(
  sourceId: number,
  base?: string,
): Promise<RightsInfo> {
  const r = await fetch(apiUrl(`/api/v1/rights/${sourceId}/review`, base), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!r.ok) throw new Error(`review request failed: ${r.status}`);
  return r.json() as Promise<RightsInfo>;
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
