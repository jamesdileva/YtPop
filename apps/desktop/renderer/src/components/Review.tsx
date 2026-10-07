import { useCallback, useEffect, useState } from "react";
import {
  patchMoment,
  previewUrl,
  useMoments,
  type Moment,
} from "../hooks/useMoments";

function Bar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div>
      <span>
        {label} {value.toFixed(1)}
      </span>
      <div
        data-testid={`bar-${label}`}
        style={{ background: "#ddd", width: 160 }}
      >
        <div style={{ background: "#46c", width: `${pct}%`, height: 8 }} />
      </div>
    </div>
  );
}

/** Shortcuts: A approve · R reject · J/K next/prev · Z/X trim start −/+1s · C/V trim end −/+1s */
export default function Review() {
  const [filter, setFilter] = useState("CANDIDATE");
  const { data, loading, refresh } = useMoments(filter);
  const [selected, setSelected] = useState(0);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");

  const current: Moment | undefined = data[selected];

  useEffect(() => {
    setSelected(0);
    if (data[0]) {
      setStart(String(data[0].start_time));
      setEnd(String(data[0].end_time));
    }
  }, [data]);

  const decide = useCallback(
    async (status: "APPROVED" | "REJECTED") => {
      if (!current) return;
      await patchMoment(current.id, { status, reason });
      setReason("");
      refresh();
    },
    [current, reason, refresh],
  );

  const trim = useCallback(async () => {
    if (!current) return;
    await patchMoment(current.id, {
      start_time: Number(start),
      end_time: Number(end),
      reason: reason || "manual trim",
    });
    refresh();
  }, [current, start, end, reason, refresh]);

  const nudge = useCallback(
    async (field: "start" | "end", delta: number) => {
      if (!current) return;
      const s = field === "start" ? current.start_time + delta : current.start_time;
      const e = field === "end" ? current.end_time + delta : current.end_time;
      if (e > s && s >= 0) {
        await patchMoment(current.id, { start_time: s, end_time: e, reason: "nudge" });
        refresh();
      }
    },
    [current, refresh],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      const k = e.key.toLowerCase();
      if (k === "a") void decide("APPROVED");
      else if (k === "r") void decide("REJECTED");
      else if (k === "j") setSelected((s) => Math.min(s + 1, data.length - 1));
      else if (k === "k") setSelected((s) => Math.max(s - 1, 0));
      else if (k === "z") void nudge("start", -1);
      else if (k === "x") void nudge("start", 1);
      else if (k === "c") void nudge("end", -1);
      else if (k === "v") void nudge("end", 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide, nudge, data.length]);

  return (
    <section>
      <h2>Review</h2>
      <div>
        {(["CANDIDATE", "APPROVED", "REJECTED", "ALL"] as const).map((s) => (
          <button key={s} data-testid={`filter-${s}`} onClick={() => setFilter(s)}>
            {s}
          </button>
        ))}
      </div>
      {loading ? (
        <p>Loading candidates…</p>
      ) : data.length === 0 ? (
        <p>No candidates — run find-moments.</p>
      ) : (
        <div style={{ display: "flex", gap: 24 }}>
          <ol data-testid="review-queue">
            {data.map((m, i) => (
              <li key={m.id}>
                <button
                  data-testid={`queue-${m.id}`}
                  onClick={() => {
                    setSelected(i);
                    setStart(String(m.start_time));
                    setEnd(String(m.end_time));
                  }}
                >
                  #{m.id} {m.start_time.toFixed(1)}s [{m.final_score.toFixed(1)}]{" "}
                  {m.status}
                </button>
              </li>
            ))}
          </ol>
          {current && (
            <div data-testid="review-card">
              <video
                data-testid="review-video"
                src={previewUrl(current.id)}
                controls
                preload="none"
                width={480}
              />
              <p data-testid="review-excerpt">{current.transcript_excerpt}</p>
              <Bar label="Score" value={current.final_score} />
              <Bar label="Hook" value={current.editorial_score} />
              <Bar label="Emotion" value={current.emotion_score} />
              <Bar label="Novelty" value={current.novelty_score} />
              <Bar label="Context" value={current.semantic_score} />
              <div>
                <label>
                  Start{" "}
                  <input
                    data-testid="trim-start"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                  />
                </label>
                <label>
                  End{" "}
                  <input
                    data-testid="trim-end"
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                  />
                </label>
                <button data-testid="btn-trim" onClick={() => void trim()}>
                  Trim
                </button>
              </div>
              <div>
                <input
                  data-testid="review-reason"
                  placeholder="reason (saved to feedback)"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
                <button data-testid="btn-reject" onClick={() => void decide("REJECTED")}>
                  Reject
                </button>
                <button data-testid="btn-approve" onClick={() => void decide("APPROVED")}>
                  Approve
                </button>
              </div>
              <p>
                {current.category} {current.is_best ? "★ best" : ""} {current.notes}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
