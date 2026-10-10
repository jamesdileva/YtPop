"""Editorial overlay pack (Phase 9 / D11).

Turns an accepted editorial plan into original, inspectable overlay content:
context cards, commentary cards, source cards, comparison cards, charts,
timeline graphics, annotations and a narration script. The renderer turns
the card-graphics items into real video segments, so the output carries
original material instead of being a pure concatenation.

Deterministic and offline: no LLM call here (the plan already carries the
words). Graphics are Pillow-generated; the narration script is text plus
timing so a future TTS stage can consume it.
"""

import json
import structlog
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import models
from app.services import ffmpeg_service as ff
from app.services import graphics_service as gfx

log = structlog.get_logger()

OVERLAY_KINDS = ("context", "commentary", "source", "comparison", "chart",
                 "timeline", "annotation", "narration")


class OverlayItem(BaseModel):
    id: str
    kind: str = Field(pattern="^(" + "|".join(OVERLAY_KINDS) + ")$")
    timeline_at: float = Field(default=0.0, description="seconds into the episode")
    duration: float = 6.0
    text: str
    asset_path: str | None = None
    moment_id: int | None = None
    source_id: int | None = None


class OverlayPack(BaseModel):
    episode_id: int
    title: str
    narration: list[tuple[float, str]] = Field(default_factory=list)
    items: list[OverlayItem] = Field(default_factory=list)


class OverlayError(RuntimeError):
    pass


def _load_cfg(cfg: dict | None) -> dict:
    if cfg is not None:
        return cfg
    import yaml

    from app.db.database import repo_root

    path = repo_root() / "configs" / "editorial.yaml"
    data = {}
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    return data.get("overlays") or {}


def build_overlays(db: Session, episode_id: int, plan,
                   cfg: dict | None = None,
                   roots: list[Path] | None = None) -> dict:
    settings = _load_cfg(cfg)
    base = (roots or [ff.repo_data_dir()])[0]
    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise OverlayError(f"episode not found: {episode_id}")
    segs = (db.query(models.EpisodeSegment)
            .filter_by(episode_id=episode_id)
            .order_by(models.EpisodeSegment.sequence.asc()).all())

    clip_segs = [s for s in segs if s.moment_id is not None]
    if not clip_segs:
        raise OverlayError(f"episode {episode_id} has no clip segments")

    # timeline offsets: clips first, then overlay cards (matching the renderer)
    clip_total = sum(s.duration for s in clip_segs)
    card_at = clip_total
    items: list[OverlayItem] = []
    narration: list[tuple[float, str]] = [(0.0, plan.opening_hook)]
    sources: dict[int, models.Source] = {}

    # context + commentary cards ride with their clip's end
    for seg in clip_segs:
        if seg.context_text:
            items.append(OverlayItem(
                id=f"ctx-{seg.id}", kind="context", timeline_at=seg_at(segs, seg),
                duration=float(settings.get("context_seconds", 4.0)),
                text=seg.context_text, moment_id=seg.moment_id))
        if seg.commentary_text:
            items.append(OverlayItem(
                id=f"cmt-{seg.id}", kind="commentary",
                timeline_at=seg_at(segs, seg) + seg.duration,
                duration=float(settings.get("commentary_seconds", 4.0)),
                text=seg.commentary_text, moment_id=seg.moment_id))

    # comparison card when a cluster contributed more than one clip
    by_cluster: dict[str, list[int]] = {}
    for cluster in plan.story_clusters:
        ids = [i for i in cluster.moment_ids
               if any(s.moment_id == i for s in clip_segs)]
        if len(ids) > 1:
            by_cluster[cluster.name] = ids
    for name, ids in by_cluster.items():
        items.append(OverlayItem(
            id=f"cmp-{name}", kind="comparison", timeline_at=card_at,
            duration=float(settings.get("comparison_seconds", 6.0)),
            text=f"{name}: {len(ids)} moments compared", moment_id=ids[0]))

    # source cards: one per clip's origin (channel + title)
    for i, seg in enumerate(clip_segs):
        moment = db.get(models.Moment, seg.moment_id)
        if moment is None:
            continue
        src = db.get(models.Source, moment.source_id)
        if src is None:
            continue
        sources[src.id] = src
        items.append(OverlayItem(
            id=f"src-{src.id}", kind="source", timeline_at=card_at + i * 1.0,
            duration=float(settings.get("source_seconds", 5.0)),
            text=f"{src.channel_name or 'Unknown'} — {src.title}",
            source_id=src.id))

    # chart: views by contributing source (original graphic)
    chart_rows = sorted(
        ((s.channel_name or s.external_id, s.view_count) for s in sources.values()),
        key=lambda r: r[1], reverse=True)
    chart_item = None
    if chart_rows and settings.get("charts", True):
        path = gfx.bar_chart(
            ff.resolve_data_path(Path("overlays") / f"chart_{episode_id}.png",
                                [base]),
            [(label, views) for label, views in chart_rows],
            title=f"Where the views came from — {plan.title}")
        chart_item = OverlayItem(
            id=f"chart-{episode_id}", kind="chart", timeline_at=card_at,
            duration=float(settings.get("chart_seconds", 6.0)),
            text="Views by source", asset_path=str(path))
        items.append(chart_item)

    # timeline graphic: episode structure
    if settings.get("timeline_graphic", True):
        strip_rows = [("intro", 4.0)] + [
            (f"clip {i + 1}", s.duration) for i, s in enumerate(clip_segs)
        ] + [("outro", 5.0)]
        path = gfx.timeline_strip(
            ff.resolve_data_path(Path("overlays") / f"timeline_{episode_id}.png",
                                [base]),
            strip_rows)
        items.append(OverlayItem(
            id=f"timeline-{episode_id}", kind="timeline", timeline_at=card_at,
            duration=float(settings.get("timeline_seconds", 5.0)),
            text="Episode timeline", asset_path=str(path)))

    # annotations: lower-third text over each clip (burned in by renderer)
    for i, seg in enumerate(clip_segs):
        start = seg_at(segs, seg)
        items.append(OverlayItem(
            id=f"ann-{seg.id}", kind="annotation", timeline_at=start,
            duration=float(settings.get("annotation_seconds", 5.0)),
            text=plan.title if i == 0 else f"{plan.title} · part {i + 1}",
            moment_id=seg.moment_id))

    # narration script: hook -> per-clip take -> ending
    for i, seg in enumerate(clip_segs):
        line = seg.context_text or seg.commentary_text or plan.ending
        narration.append((seg_at(segs, seg), line))
    narration.append((clip_total, plan.ending))

    pack = OverlayPack(episode_id=episode_id, title=plan.title,
                       narration=narration, items=items)
    # replace this pass's overlay cards, then append the new set so building
    # twice never duplicates segments (transition_type marks them ours)
    db.query(models.EpisodeSegment).filter_by(
        episode_id=episode_id, transition_type="overlay").delete()
    next_seq = max([s.sequence for s in segs], default=-1) + 1
    for item in items:
        if item.kind in ("annotation", "narration", "context", "commentary"):
            continue  # burned in / spoken, not standalone cards
        label = item.text
        if item.asset_path:
            label = f"overlay:{item.asset_path}"
        db.add(models.EpisodeSegment(
            episode_id=episode_id, moment_id=None, sequence=next_seq,
            duration=item.duration, transition_type="overlay",
            context_text=label))
        next_seq += 1
    db.flush()
    _persist(db, pack, base, episode_id)
    log.info("overlays_built", episode_id=episode_id, items=len(items),
             kinds=sorted({i.kind for i in items}))
    return {
        "episode_id": episode_id,
        "items": [i.model_dump() for i in items],
        "narration": [[t, l] for t, l in narration],
        "kinds": sorted({i.kind for i in items}),
        "cards_at_seconds": round(card_at, 3),
        "artifact": str(ff.resolve_data_path(
            Path("overlays") / f"{episode_id}.json", [base])),
    }


def seg_at(segs: list, seg) -> float:
    total = 0.0
    for s in segs:
        if s.id == seg.id:
            return round(total, 3)
        total += s.duration
    return 0.0


def _persist(db: Session, pack: OverlayPack, base: Path,
             episode_id: int) -> dict:
    artifact = ff.resolve_data_path(Path("overlays") / f"{episode_id}.json",
                                   [base])
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    db.query(models.MediaAsset).filter_by(
        source_id=_pack_source_id(db, episode_id), kind="overlay").delete()
    for item in pack.items:
        if not item.asset_path:
            continue
        db.add(models.MediaAsset(
            source_id=_pack_source_id(db, episode_id), kind="overlay",
            path=item.asset_path, codec=item.kind))
    db.flush()
    return {"artifact": str(artifact)}


def _pack_source_id(db: Session, episode_id: int) -> int:
    seg = (db.query(models.EpisodeSegment)
           .filter_by(episode_id=episode_id)
           .filter(models.EpisodeSegment.moment_id.is_not(None)).first())
    if seg is None:
        raise OverlayError(f"episode {episode_id} has no clip segments")
    moment = db.get(models.Moment, seg.moment_id)
    if moment is None:
        raise OverlayError("moment missing for overlay linkage")
    return moment.source_id
