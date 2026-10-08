"""Trend intelligence (S11): embeddings → clusters → trend_events.

Single-link agglomerative clustering over title+description embeddings,
then a 6-component trend score (weights in configs/default.yaml, tunable
without redeploy). Topic titles come from the summarizer LLM with a
deterministic keyword fallback so the pipeline works fully offline.
"""

import math
import structlog
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.db import models
from app.domain.discovery import service as discovery

log = structlog.get_logger()


class TrendError(RuntimeError):
    pass


DEFAULT_TRENDS: dict = {
    "similarity_threshold": 0.55,
    "min_sources": 2,
    "weights": {
        "views_velocity": 0.25, "engagement_velocity": 0.15,
        "recency": 0.15, "cross_source": 0.20, "momentum": 0.15,
        "novelty": 0.10,
    },
    "views_velocity_cap": 10000.0,
    "engagement_velocity_cap": 1000.0,
    "cross_source_cap": 5,
    "recency_half_life_hours": 24.0,
    # D2: log compression keeps magnitude differences visible after the
    # cap is reached (linear mode saturates and ties distinct topics).
    "log_scale": True,
}


def _check_weights(cfg: dict) -> None:
    total = sum(cfg["weights"].values())
    if not math.isclose(total, 1.0, abs_tol=0.01):
        raise TrendError(f"trend weights must sum to 1.0, got {total}")


def load_trend_config(path: str | Path | None = None) -> dict:
    cfg = deepcopy(DEFAULT_TRENDS)
    if path is None:
        from app.db.database import repo_root

        candidate = repo_root() / "configs" / "default.yaml"
    else:
        candidate = Path(path)
    if candidate.is_file():
        with open(candidate, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        for key, value in (loaded.get("trends") or {}).items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value
    total = sum(cfg["weights"].values())
    _check_weights(cfg)
    return cfg


def _cosine(a: list[float], b: list[float]) -> float:
    denom = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    if denom == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / denom


def _embed_text(source: models.Source) -> str:
    return f"{source.title or ''} {(source.description or '')[:200]}".strip()


def cluster_sources(vectors: list[list[float]], threshold: float) -> list[list[int]]:
    """Single-link clusters as index groups (deterministic, sorted)."""
    n = len(vectors)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for i in range(n):
        for j in range(i + 1, n):
            if _cosine(vectors[i], vectors[j]) >= threshold:
                union(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return sorted([sorted(g) for g in groups.values()], key=lambda g: g[0])


def _utc(dt) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _snapshots(db: Session, source_id: int) -> list:
    from sqlalchemy import select

    return list(db.execute(
        select(models.SourceSnapshot)
        .where(models.SourceSnapshot.source_id == source_id)
        .order_by(models.SourceSnapshot.taken_at.asc())
    ).scalars().all())


def _velocity_between(first, last) -> float:
    hours = (_utc(last.taken_at) - _utc(first.taken_at)).total_seconds() / 3600
    if hours <= 0:
        return 0.0
    return (last.view_count - first.view_count) / hours


def _eng_velocity_between(first, last) -> float:
    hours = (_utc(last.taken_at) - _utc(first.taken_at)).total_seconds() / 3600
    if hours <= 0:
        return 0.0
    return ((last.like_count + last.comment_count)
            - (first.like_count + first.comment_count)) / hours


def _component(value: float, cap: float, log_scale: bool) -> float:
    """Normalize a raw quantity to 0..100 against `cap`.

    Linear mode saturates: value >= cap scores 100, collapsing magnitude
    differences (two topics tied at 92.5 in S11). Saturating (default) mode
    treats `cap` as the half-saturation point: value == cap -> 50, 9x cap ->
    90, and the top compresses without ever tying distinct magnitudes.
    Near-zero stays numerically identical to linear mode.
    """
    value = max(float(value), 0.0)
    cap = max(float(cap), 1e-9)
    if log_scale:
        return 100.0 * value / (value + cap)
    return 100.0 * min(value / cap, 1.0)


def score_cluster(db: Session, members: list[models.Source],
                  cfg: dict, novelty: float = 100.0) -> dict:
    """Six 0..100 components + weighted score."""
    now = datetime.now(timezone.utc)
    vel = sum(discovery.compute_velocity(db, m.id) for m in members)
    eng_vel = 0.0
    momentums = []
    for m in members:
        snaps = _snapshots(db, m.id)
        if snaps:
            eng_vel += _eng_velocity_between(snaps[0], snaps[-1])
        if len(snaps) >= 3:
            mid = snaps[len(snaps) // 2]
            early = _velocity_between(snaps[0], mid)
            recent = _velocity_between(mid, snaps[-1])
            momentums.append(min(100.0, 50.0 * recent / max(early, 1e-9)))
    first_seen = min((_utc(m.discovered_at) for m in members),
                     default=now)
    age_h = max((now - first_seen).total_seconds() / 3600, 0.0)
    half = float(cfg["recency_half_life_hours"])
    log_scale = bool(cfg.get("log_scale", True))
    components = {
        "views_velocity": _component(vel, cfg["views_velocity_cap"], log_scale),
        "engagement_velocity": _component(
            eng_vel, cfg["engagement_velocity_cap"], log_scale),
        "recency": 100.0 * math.exp(-age_h / half),
        "cross_source": _component(len(members), cfg["cross_source_cap"],
                                   log_scale),
        "momentum": sum(momentums) / len(momentums) if momentums else 50.0,
        "novelty": max(0.0, min(100.0, novelty)),
    }
    w = cfg["weights"]
    score = round(sum(components[k] * w[k] for k in components), 3)
    return {"score": score, "velocity": round(vel, 2), "components": {
        k: round(v, 2) for k, v in components.items()}}


def fallback_topic(members: list[models.Source]) -> tuple[str, str]:
    """Deterministic keyword title when the LLM is unavailable."""
    words = Counter()
    for m in members:
        for tok in (m.title or "").lower().split():
            clean = tok.strip(".,!?;:\"'()").lower()
            if len(clean) > 3:
                words[clean] += 1
    top = [w for w, _ in words.most_common(3)]
    title = " ".join(w.capitalize() for w in top) or "Untitled topic"
    desc = "; ".join(sorted({(m.title or "")[:80] for m in members}))[:500]
    return title, desc


def summarize_topic(members: list[models.Source], llm=None) -> tuple[str, str]:
    """LLM topic title/description with keyword fallback (offline-safe)."""
    if llm is None:
        return fallback_topic(members)
    titles = [m.title for m in members]
    try:
        raw = llm.chat_json(
            "You name trending video topics. Reply with a single JSON object "
            '{"topic": short title, "description": one sentence}.',
            "Video titles:\n" + "\n".join(f"- {t}" for t in titles),
        )
        topic = str(raw.get("topic", "")).strip()
        desc = str(raw.get("description", "")).strip()
        if topic:
            return topic[:120], desc[:500]
    except Exception as e:
        log.info("topic_llm_fallback", error=str(e)[:200])
    return fallback_topic(members)


def _existing_member_ids(db: Session, trend_id: int) -> set[int]:
    from sqlalchemy import select

    return set(db.execute(
        select(models.TrendSource.source_id)
        .where(models.TrendSource.trend_id == trend_id)
    ).scalars().all())


def cluster_trends(db: Session, region: str = "US", category: str = "",
                   threshold: float | None = None, min_sources: int | None = None,
                   cfg: dict | None = None, embed_fn=None, llm=None) -> dict:
    """One clustering run: embed → group → score → upsert trend_events."""
    cfg = cfg or load_trend_config()
    _check_weights(cfg)
    threshold = threshold if threshold is not None else float(cfg["similarity_threshold"])
    min_sources = min_sources if min_sources is not None else int(cfg["min_sources"])
    q = db.query(models.Source)
    if category:
        q = q.filter_by(category=category)
    sources = sorted(q.all(), key=lambda s: s.id)
    if not sources:
        return {"trends": [], "clusters": 0, "sources": 0}
    if embed_fn is None:
        from app.domain.clipping.service import Embedder

        embed_fn = Embedder().encode
    vectors = embed_fn([_embed_text(s) for s in sources])

    # novelty baseline: embeddings of existing ACTIVE trend topics
    active = db.query(models.TrendEvent).filter_by(status="ACTIVE").all()
    active_vecs: list[tuple[int, list[float]]] = []
    if active:
        texts = [f"{t.topic} {t.description or ''}" for t in active]
        for trend, vec in zip(active, embed_fn(texts)):
            active_vecs.append((trend.id, vec))

    results = []
    for group in cluster_sources(vectors, threshold):
        if len(group) < min_sources:
            continue
        members = [sources[i] for i in group]
        member_ids = {m.id for m in members}
        topic_vec = [sum(v[i] for v in [vectors[g] for g in group]) / len(group)
                     for i in range(len(vectors[0]))]
        novelty = 100.0
        for _, avec in active_vecs:
            novelty = min(novelty, (1.0 - max(0.0, _cosine(topic_vec, avec))) * 100)
        scored = score_cluster(db, members, cfg, novelty)
        topic, desc = summarize_topic(members, llm)
        majority_cat = Counter(m.category or "" for m in members).most_common(1)[0][0]

        # match an existing ACTIVE trend by member overlap (>=50% Jaccard)
        match = None
        for t in active:
            existing = _existing_member_ids(db, t.id)
            union = existing | member_ids
            jaccard = len(existing & member_ids) / len(union) if union else 0.0
            if jaccard >= 0.5:
                match = t
                break
        if match is not None:
            match.topic = topic
            match.description = desc
            match.score = scored["score"]
            match.velocity = scored["velocity"]
            match.last_detected_at = datetime.now(timezone.utc)
            added = sorted(member_ids - _existing_member_ids(db, match.id))
            for sid in added:
                db.add(models.TrendSource(
                    trend_id=match.id, source_id=sid,
                    relevance_score=1.0, relationship_type="related"))
            trend_id = match.id
            created = False
        else:
            row = models.TrendEvent(
                topic=topic, description=desc, score=scored["score"],
                velocity=scored["velocity"], region=region,
                category=majority_cat, status="ACTIVE",
            )
            db.add(row)
            db.flush()
            best = max(members, key=lambda m: m.trend_score)
            for m in members:
                db.add(models.TrendSource(
                    trend_id=row.id, source_id=m.id,
                    relevance_score=round(m.trend_score, 3),
                    relationship_type="primary" if m.id == best.id else "related"))
            trend_id = row.id
            created = True
        results.append({
            "trend_id": trend_id, "topic": topic, "created": created,
            "sources": len(members), **scored,
        })
        log.info("trend_clustered", trend_id=trend_id, topic=topic,
                 sources=len(members), score=scored["score"])
    db.add(models.Job(
        type="CLUSTER_TRENDS", status="COMPLETED", priority=30,
        payload_json=f'{{"region": "{region}", "trends": {len(results)}}}',
        progress=1.0, attempts=1,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    ))
    db.commit()
    return {"trends": results, "clusters": len(results), "sources": len(sources)}
