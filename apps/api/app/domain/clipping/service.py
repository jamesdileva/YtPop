"""Clip detection (S6 V1/V2, S14 V3/V4/V5-preview).

V1 keyword-only (embed_fn=None). V2 adds embedding similarity + MMR.
V3 LLM judge, V4 cheap vision and V5 learned ranker sit behind flags in
configs/scoring.yaml (all default off except the V1/V2 path).
Vision/LLM only ever see finalist windows, never full videos.

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
        "non_overlap": True,
        "max_overlap": 0.5,
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
    "scoring_version": "v2",
    "vision": {"enabled": False, "fps": 1, "weight": 10.0,
               "finalist_multiplier": 3},
    "llm_scoring": {"enabled": False, "weight": 10.0},
    "learned_ranking": {"enabled": False, "path": ""},
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

def _overlap_ratio(a: dict, b: dict) -> float:
    """Intersection as a fraction of the *shorter* window (0..1)."""
    inter = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    shorter = min(a["end"] - a["start"], b["end"] - b["start"])
    return inter / shorter if shorter > 0 else 0.0


def _mmr_order(scored: list[dict], vectors: list[list[float]] | None,
               texts: list[str], weights: dict) -> list[int]:
    """Greedy MMR ranking over all indices: score − redundancy to picked."""
    remaining = list(range(len(scored)))
    picked: list[int] = []
    adjusted = {i: scored[i]["final_score"] for i in remaining}
    while remaining:
        if picked:
            for i in remaining:
                if vectors is not None:
                    sim = max(_cosine(vectors[i], vectors[p])
                              for p in picked)
                else:
                    sim = max(_jaccard(texts[i], texts[p]) for p in picked)
                adjusted[i] = scored[i]["final_score"] - weights["redundancy"] * sim
        best = max(remaining, key=lambda i: adjusted[i])
        picked.append(best)
        remaining.remove(best)
    return picked


def _suppress_overlaps(order: list[int], scored: list[dict], top_k: int,
                       max_overlap: float) -> list[int]:
    """Greedy score-ordered picks that stay under an overlap threshold.

    Strict first (max_overlap). If that starves the list below top_k, relax
    once to 0.9 (near-duplicate suppression, not timed duplicates such as
    an intro + payoff). It deliberately never relaxes to "anything goes" —
    a short clip yields fewer, genuinely distinct candidates instead of a
    top-k padded with near-copies of the same coverage.
    """
    for threshold in (max_overlap, 0.9):
        kept: list[int] = []
        for i in order:
            if len(kept) >= top_k:
                break
            if any(_overlap_ratio(scored[i], scored[j]) > threshold
                   for j in kept):
                continue
            kept.append(i)
        if len(kept) >= min(top_k, len(order)):
            return kept
    return kept


def select_top(
    scored: list[dict], vectors: list[list[float]] | None,
    texts: list[str], top_k: int, weights: dict,
    windows: dict | None = None,
) -> list[int]:
    """MMR order, then optional time-overlap suppression (D1).

    MMR alone can't keep duplicate time windows out of the top-k — its
    penalty is bounded while the score spread is not — so overlapping
    candidates are dropped after ranking when windows.non_overlap is on.
    """
    order = _mmr_order(scored, vectors, texts, weights)
    cfg = windows if windows is not None else DEFAULT_SCORING["windows"]
    if not cfg.get("non_overlap", True):
        return order[:top_k]
    max_overlap = float(cfg.get("max_overlap", 0.5))
    return _suppress_overlaps(order, scored, top_k, max_overlap)


# --- V3/V4 finalist judges -----------------------------------------------------

def _score_finalists_llm(scored: list[dict], finalists: list[int],
                         texts: list[str], llm, cfg: dict) -> None:
    """V3: ask the classifier 'is this actually interesting?' (0..1)."""
    if not ((cfg.get("llm_scoring") or {}).get("enabled") and llm):
        return
    weight = float(cfg["llm_scoring"].get("weight", 10.0))
    numbered = "\n".join(f"[{i}] {texts[i][:300]}" for i in finalists)
    try:
        raw = llm.chat_json(
            "You rate video moments. Reply with a single JSON object "
            '{"scores": {"<index>": 0.0-1.0}} using the [index] numbers given.',
            f"Rate how interesting each moment is:\n{numbered}")
        scores = raw.get("scores", {}) if isinstance(raw, dict) else {}
    except Exception as e:
        log.info("llm_scoring_fallback", error=str(e)[:200])
        return
    for i in finalists:
        try:
            s = max(0.0, min(1.0, float(scores.get(str(i), scores.get(i, 0.0)))))
        except (TypeError, ValueError):
            s = 0.0
        scored[i]["llm_score"] = round(s, 3)
        scored[i]["final_score"] = round(scored[i]["final_score"] + s * weight, 3)
    log.info("llm_scored", n=len(finalists))


def _score_finalists_visual(db: Session, source_id: int, scored: list[dict],
                            finalists: list[int], cfg: dict,
                            roots: list[Path] | None = None) -> None:
    """V4: cheap luma-motion interest for finalist windows."""
    vision_cfg = cfg.get("vision") or {}
    if not vision_cfg.get("enabled"):
        return
    from app.domain.clipping import vision as vision_mod

    media = None
    for kind in ("normalized", "raw"):
        asset = (
            db.query(models.MediaAsset)
            .filter_by(source_id=source_id, kind=kind)
            .order_by(models.MediaAsset.id.desc()).first()
        )
        if asset is not None:
            from pathlib import Path as _Path

            if _Path(asset.path).is_file():
                media = _Path(asset.path)
                break
    if media is None:
        log.info("vision_skipped", reason="no media")
        return
    weight = float(vision_cfg.get("weight", 10.0))
    fps = int(vision_cfg.get("fps", 1))
    for i in finalists:
        try:
            s = vision_mod.score_window_visual(
                media, scored[i]["start"], scored[i]["end"], fps=fps,
                roots=roots)
        except Exception as e:
            log.info("vision_fallback", error=str(e)[:200])
            continue
        scored[i]["visual_score"] = s
        scored[i]["final_score"] = round(scored[i]["final_score"] + s * weight, 3)
    log.info("vision_scored", n=len(finalists))


# --- pipeline ------------------------------------------------------------------

def find_moments(
    db: Session, source_id: int, top_k: int | None = None,
    weights_cfg: dict | None = None, embed_fn=None,
    use_embeddings: bool = True, llm=None,
    roots: list[Path] | None = None,
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
            "visual_score": 0.0, "llm_score": 0.0,
            "final_score": round(base, 3),
        })

    # V5 learned ranker (passthrough until a weights file exists)
    learned = (cfg.get("learned_ranking") or {})
    if learned.get("enabled"):
        from app.domain.clipping import ranker
        scored = ranker.apply(
            scored, ranker.load_weights(learned.get("path")))

    # V3/V4 run on finalists only (never full videos)
    finalist_n = min(len(scored),
                     max(top_k * int(cfg.get("vision", {}).get(
                         "finalist_multiplier", 3)), top_k))
    finalists = sorted(range(len(scored)),
                       key=lambda i: scored[i]["final_score"],
                       reverse=True)[:finalist_n]
    _score_finalists_llm(scored, finalists, texts, llm, cfg)
    _score_finalists_visual(db, source_id, scored, finalists, cfg, roots)

    order = select_top(
        scored, vectors, texts, min(top_k, len(scored)), cfg["weights"],
        windows=w,
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
            visual_score=cand.get("visual_score", 0.0),
            editorial_score=cand["feats"]["hook"],
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
