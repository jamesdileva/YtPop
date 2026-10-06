"""Clip detection V1/V2 (S6): transcript windows + keyword/semantic scoring.

V1 (keyword) runs with embed_fn=None. V2 adds embedding similarity for
semantic relevance + MMR redundancy. Vision/LLM judges arrive in later
sprints — the selection interface stays the same.

All candidates are stored (never delete low scores); selection only orders.
"""

import math
import structlog
from copy import deepcopy
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models

log = structlog.get_logger()


class ClipError(RuntimeError):
    pass


DEFAULT_SCORING: dict = {
    "windows": {
        "min_duration": 5.0,
        "max_duration": 90.0,
        "target_candidates_per_video": 10,
        "max_segments_per_window": 8,
    },
    "weights": {
        "hook": 20.0, "relevance": 15.0, "novelty": 10.0,
        "emotion": 15.0, "payoff": 10.0, "completeness": 5.0,
        "semantic_relevance": 15.0, "semantic_novelty": 10.0,
        "redundancy": 25.0, "dead_air": 15.0,
        "context_dependency": 10.0,
    },
    "hook_words": [], "emotion_words": [], "payoff_words": [],
    "dangling_starts": [], "min_wps": 1.2,
}


def repo_root() -> Path:
    from app.db.database import repo_root as _root

    return _root()


def load_scoring(path: str | Path | None = None) -> dict:
    """Load scoring.yaml over defaults (weights editable without code)."""
    cfg = deepcopy(DEFAULT_SCORING)
    candidate = Path(path) if path else repo_root() / "configs" / "scoring.yaml"
    if candidate.is_file():
        with open(candidate, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        for key, value in loaded.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value
    return cfg


# --- windows ---------------------------------------------------------------

def build_windows(
    segments: list[dict], min_dur: float, max_dur: float, max_segs: int
) -> list[dict]:
    """Sliding windows of 1..max_segs consecutive segments within duration."""
    windows = []
    n = len(segments)
    for i in range(n):
        words: list[str] = []
        for j in range(i, min(i + max_segs, n)):
            seg = segments[j]
            words.append(seg.get("text", ""))
            start = float(segments[i].get("start", 0.0))
            end = float(seg.get("end", start))
            dur = end - start
            if dur < min_dur:
                continue
            if dur > max_dur:
                break
            text = " ".join(words).strip()
            if text:
                windows.append({
                    "start": round(start, 3), "end": round(end, 3),
                    "text": text, "seg_count": j - i + 1,
                })
    return windows


# --- keyword features (0..1 each) --------------------------------------------

def _hits(text: str, phrases: list[str]) -> float:
    low = text.lower()
    return sum(1 for p in phrases if p.lower() in low)


def keyword_features(text: str, topic_words: set[str], cfg: dict) -> dict:
    low = text.lower().strip()
    words = low.split()
    n = max(len(words), 1)
    hook = min(_hits(low, cfg.get("hook_words", [])) * 0.4, 1.0)
    if "?" in text:
        hook = min(hook + 0.4, 1.0)
    if "!" in text:
        hook = min(hook + 0.2, 1.0)
    content = {w.strip(".,!?;:\"'()") for w in words}
    relevance = len(content & topic_words) / max(len(topic_words), 1)
    relevance = min(relevance, 1.0)
    novelty = len(set(words)) / n
    emotion = min(_hits(low, cfg.get("emotion_words", [])) * 0.5, 1.0)
    payoff = min(_hits(low, cfg.get("payoff_words", [])) * 0.5, 1.0)
    completeness = 1.0 if text.rstrip().endswith((".", "?", "!")) else 0.3
    dur_words = max(len(words), 1)
    wps = dur_words / 10.0  # approx; refined with real duration by caller
    dead_air = max(0.0, 1.0 - wps / float(cfg.get("min_wps", 1.2)))
    context_dependency = 1.0 if any(
        low.startswith(d) for d in cfg.get("dangling_starts", [])
    ) else 0.0
    return {
        "hook": round(hook, 3), "relevance": round(relevance, 3),
        "novelty": round(novelty, 3), "emotion": round(emotion, 3),
        "payoff": round(payoff, 3),
        "completeness": round(completeness, 3),
        "dead_air": round(min(dead_air, 1.0), 3),
        "context_dependency": context_dependency,
    }


def refine_dead_air(feats: dict, text: str, duration: float, cfg: dict) -> None:
    words = len(text.split())
    wps = words / max(duration, 0.1)
    feats["dead_air"] = round(
        min(max(0.0, 1.0 - wps / float(cfg.get("min_wps", 1.2))), 1.0), 3
    )


def score_window(feats: dict, weights: dict) -> float:
    positives = (
        feats["hook"] * weights["hook"]
        + feats["relevance"] * weights["relevance"]
        + feats["novelty"] * weights["novelty"]
        + feats["emotion"] * weights["emotion"]
        + feats["payoff"] * weights["payoff"]
        + feats["completeness"] * weights["completeness"]
    )
    penalties = (
        feats["dead_air"] * weights["dead_air"]
        + feats["context_dependency"] * weights["context_dependency"]
    )
    return round(max(positives - penalties, 0.0), 3)


# --- embeddings (V2) ----------------------------------------------------------

class Embedder:
    """Lazy all-MiniLM-L6-v2; encode() returns L2-normalized vectors."""

    MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: str = MODEL) -> None:
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            log.info("embedder_load", model=self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        vecs = self.model.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in np.asarray(vecs)]


def _cosine(a: list[float], b: list[float]) -> float:
    denom = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    if denom == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / denom


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# --- selection ---------------------------------------------------------------

def select_top(
    scored: list[dict], vectors: list[list[float]] | None,
    texts: list[str], top_k: int, weights: dict,
) -> list[int]:
    """Greedy MMR order over indices: score minus redundancy to picked."""
    remaining = list(range(len(scored)))
    picked: list[int] = []
    adjusted = {i: scored[i]["final_score"] for i in remaining}
    while remaining and len(picked) < top_k:
        if picked:
            for i in remaining:
                if vectors is not None:
                    sim = max(_cosine(vectors[i], vectors[p]) for p in picked)
                else:
                    sim = max(_jaccard(texts[i], texts[p]) for p in picked)
                adjusted[i] = scored[i]["final_score"] - weights["redundancy"] * sim
        best = max(remaining, key=lambda i: adjusted[i])
        picked.append(best)
        remaining.remove(best)
    return picked


# --- pipeline ------------------------------------------------------------------

def find_moments(
    db: Session, source_id: int, top_k: int | None = None,
    weights_cfg: dict | None = None, embed_fn=None,
    use_embeddings: bool = True,
) -> dict:
    source = db.get(models.Source, source_id)
    if source is None:
        raise ClipError(f"source not found: {source_id}")
    tr = (
        db.query(models.Transcript)
        .filter_by(source_id=source_id)
        .order_by(models.Transcript.id.desc())
        .first()
    )
    if tr is None:
        raise ClipError(f"source {source_id} has no transcript — transcribe first")
    import json as _json

    segments = _json.loads(tr.segments_json)
    if not segments:
        raise ClipError(f"transcript for source {source_id} is empty")
    cfg = weights_cfg or load_scoring()
    w = cfg["windows"]
    top_k = top_k or int(w["target_candidates_per_video"])
    topic_words = {
        tok.strip(".,!?;:\"'()").lower()
        for tok in (source.title or "").split() if len(tok) > 2
    }

    windows = build_windows(
        segments, float(w["min_duration"]), float(w["max_duration"]),
        int(w["max_segments_per_window"]),
    )
    if not windows:
        raise ClipError("no windows in 5–90s range for this transcript")

    texts = [x["text"] for x in windows]
    vectors: list[list[float]] | None = None
    topic_vec: list[float] | None = None
    if use_embeddings:
        fn = embed_fn or Embedder().encode
        vectors = fn(texts + [source.title or "video"])
        topic_vec = vectors[-1]
        vectors = vectors[:-1]

    scored = []
    for idx, win in enumerate(windows):
        feats = keyword_features(win["text"], topic_words, cfg)
        refine_dead_air(feats, win["text"], win["end"] - win["start"], cfg)
        base = score_window(feats, cfg["weights"])
        sem_rel, sem_nov = 0.0, feats["novelty"]
        if vectors is not None and topic_vec is not None:
            sem_rel = round((_cosine(vectors[idx], topic_vec) + 1) / 2, 3)
            others = [v for j, v in enumerate(vectors) if j != idx]
            if others:
                sem_nov = round(
                    1.0 - max(0.0, max(_cosine(vectors[idx], o) for o in others)), 3
                )
            base += (
                sem_rel * cfg["weights"]["semantic_relevance"]
                + sem_nov * cfg["weights"]["semantic_novelty"]
            )
        scored.append({
            **win, "feats": feats,
            "semantic_relevance": sem_rel, "semantic_novelty": sem_nov,
            "final_score": round(base, 3),
        })

    order = select_top(
        scored, vectors, texts, min(top_k, len(scored)), cfg["weights"]
    )
    top_set = set(order)

    db.query(models.Moment).filter_by(source_id=source_id).delete()
    for rank, cand in enumerate(
        sorted(scored, key=lambda c: c["final_score"], reverse=True)
    ):
        mtype = "question" if "?" in cand["text"] else "highlight"
        db.add(models.Moment(
            source_id=source_id, start_time=cand["start"],
            end_time=cand["end"],
            transcript_excerpt=cand["text"][:500], moment_type=mtype,
            semantic_score=cand["semantic_relevance"],
            emotion_score=cand["feats"]["emotion"],
            novelty_score=cand["semantic_novelty"],
            visual_score=0.0, editorial_score=cand["feats"]["hook"],
            final_score=cand["final_score"], status="CANDIDATE",
        ))
    db.flush()
    top = [
        {
            "start": scored[i]["start"], "end": scored[i]["end"],
            "text": scored[i]["text"][:200],
            "final_score": scored[i]["final_score"],
        }
        for i in order if i in top_set
    ]
    log.info("moments_found", source_id=source_id, total=len(scored),
             top=len(top))
    return {"source_id": source_id, "total": len(scored), "top": top}
