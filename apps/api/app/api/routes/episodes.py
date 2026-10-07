"""Manual episode builder (S8): order/trim/cards persisted server-side.

Segments reference moments (clip) or are title cards (moment_id null).
actual_duration is always the sum of segment durations — never set by hand.
"""

import structlog
from copy import deepcopy
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db

log = structlog.get_logger()
router = APIRouter()

DEFAULT_TEMPLATE = {
    "title_prefix": "Untitled", "format": "daily_highlights",
    "target_duration_minutes": 20, "intro_card_seconds": 4.0,
    "outro_card_seconds": 5.0, "default_transition": "cut",
}


def load_templates(path: str | Path | None = None) -> dict:
    templates = {"manual": {**DEFAULT_TEMPLATE, "title_prefix": "Untitled"}}
    candidate = Path(path) if path else (
        Path(__file__).resolve().parents[4] / "configs" / "editorial.yaml"
    )
    if candidate.is_file():
        with open(candidate, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        for name, tpl in (loaded.get("templates") or {}).items():
            merged = deepcopy(DEFAULT_TEMPLATE)
            merged.update(tpl or {})
            templates[name] = merged
    return templates


def _rollup(db: Session, episode: models.Episode) -> float:
    total = sum(
        s.duration for s in db.query(models.EpisodeSegment)
        .filter_by(episode_id=episode.id).all()
    )
    episode.actual_duration = round(total, 3)
    db.flush()
    return episode.actual_duration


def _detail(db: Session, episode: models.Episode) -> dict:
    segs = (
        db.query(models.EpisodeSegment)
        .filter_by(episode_id=episode.id)
        .order_by(models.EpisodeSegment.sequence.asc()).all()
    )
    items = [{
        "id": s.id, "moment_id": s.moment_id, "sequence": s.sequence,
        "duration": s.duration, "transition_type": s.transition_type,
        "commentary_text": s.commentary_text, "context_text": s.context_text,
        "kind": "card" if s.moment_id is None else "clip",
    } for s in segs]
    actual = _rollup(db, episode)
    return {
        "id": episode.id, "title": episode.title, "format": episode.format,
        "theme": episode.theme, "target_duration": episode.target_duration,
        "actual_duration": actual,
        "over_under": round(actual - episode.target_duration, 3),
        "status": episode.status, "segments": items,
    }


class EpisodeCreate(BaseModel):
    title: str = Field(default="", max_length=300)
    template: str = Field(default="daily_highlights", max_length=64)
    theme: str = Field(default="", max_length=128)


class EpisodePatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    theme: str | None = Field(default=None, max_length=128)
    format: str | None = Field(default=None, max_length=64)
    target_duration: float | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, max_length=32)


class SegmentAdd(BaseModel):
    moment_id: int | None = None
    duration: float | None = Field(default=None, gt=0)
    transition_type: str = Field(default="", max_length=32)
    commentary_text: str = Field(default="", max_length=2000)
    context_text: str = Field(default="", max_length=2000)


class SegmentPatch(BaseModel):
    duration: float | None = Field(default=None, gt=0)
    transition_type: str | None = Field(default=None, max_length=32)
    commentary_text: str | None = Field(default=None, max_length=2000)
    context_text: str | None = Field(default=None, max_length=2000)


class RebuildRequest(BaseModel):
    segment_ids: list[int] = Field(min_length=1)


@router.post("/episodes")
def create_episode(payload: EpisodeCreate,
                   db: Session = Depends(get_db)) -> dict:
    templates = load_templates()
    tpl = templates.get(payload.template, templates["manual"])
    ep = models.Episode(
        title=payload.title or f"{tpl['title_prefix']} — untitled",
        format=tpl["format"], theme=payload.theme,
        target_duration=float(tpl["target_duration_minutes"]) * 60.0,
    )
    db.add(ep)
    db.flush()
    # intro + outro title cards from the template
    for idx, (text, dur) in enumerate([
        ("intro", float(tpl["intro_card_seconds"])),
        ("outro", float(tpl["outro_card_seconds"])),
    ]):
        db.add(models.EpisodeSegment(
            episode_id=ep.id, moment_id=None, sequence=idx * 100,
            duration=dur, transition_type=tpl["default_transition"],
            context_text=text,
        ))
    db.flush()
    # normalize to 0..n
    _resequence(db, ep.id)
    db.commit()
    log.info("episode_created", episode_id=ep.id, template=payload.template)
    return _detail(db, ep)


@router.get("/episodes")
def list_episodes(db: Session = Depends(get_db)) -> list[dict]:
    return [_detail(db, ep) for ep in db.query(models.Episode).all()]


@router.get("/episodes/{episode_id}")
def get_episode(episode_id: int, db: Session = Depends(get_db)) -> dict:
    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    return _detail(db, ep)


@router.patch("/episodes/{episode_id}")
def patch_episode(episode_id: int, payload: EpisodePatch,
                  db: Session = Depends(get_db)) -> dict:
    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    for field in ("title", "theme", "format", "status"):
        value = getattr(payload, field)
        if value is not None:
            setattr(ep, field, value)
    if payload.target_duration is not None:
        ep.target_duration = payload.target_duration
    db.commit()
    return _detail(db, ep)


def _resequence(db: Session, episode_id: int) -> None:
    segs = (
        db.query(models.EpisodeSegment).filter_by(episode_id=episode_id)
        .order_by(models.EpisodeSegment.sequence.asc(),
                  models.EpisodeSegment.id.asc()).all()
    )
    for idx, seg in enumerate(segs):
        seg.sequence = idx
    db.flush()


@router.post("/episodes/{episode_id}/segments")
def add_segment(episode_id: int, payload: SegmentAdd,
                db: Session = Depends(get_db)) -> dict:
    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    duration = payload.duration
    if payload.moment_id is not None:
        moment = db.get(models.Moment, payload.moment_id)
        if moment is None:
            raise HTTPException(status_code=404, detail="moment not found")
        if moment.status != "APPROVED":
            raise HTTPException(
                status_code=400,
                detail=f"moment {moment.id} is {moment.status}, approve it first",
            )
        duration = duration or round(moment.end_time - moment.start_time, 3)
    if not duration or duration <= 0:
        raise HTTPException(
            status_code=400, detail="duration required (cards) or invalid")
    top = (
        db.query(models.EpisodeSegment).filter_by(episode_id=episode_id)
        .order_by(models.EpisodeSegment.sequence.desc()).first()
    )
    seg = models.EpisodeSegment(
        episode_id=episode_id, moment_id=payload.moment_id,
        sequence=(top.sequence + 1) if top else 0, duration=duration,
        transition_type=payload.transition_type or "cut",
        commentary_text=payload.commentary_text,
        context_text=payload.context_text,
    )
    db.add(seg)
    db.commit()
    log.info("segment_added", episode_id=episode_id, segment_id=seg.id,
             moment_id=payload.moment_id)
    return _detail(db, ep)


@router.patch("/episodes/{episode_id}/segments/{segment_id}")
def patch_segment(episode_id: int, segment_id: int, payload: SegmentPatch,
                  db: Session = Depends(get_db)) -> dict:
    seg = db.get(models.EpisodeSegment, segment_id)
    if seg is None or seg.episode_id != episode_id:
        raise HTTPException(status_code=404, detail="segment not found")
    if payload.duration is not None:
        seg.duration = payload.duration
    if payload.transition_type is not None:
        seg.transition_type = payload.transition_type
    if payload.commentary_text is not None:
        seg.commentary_text = payload.commentary_text
    if payload.context_text is not None:
        seg.context_text = payload.context_text
    db.commit()
    ep = db.get(models.Episode, episode_id)
    assert ep is not None
    return _detail(db, ep)


@router.delete("/episodes/{episode_id}/segments/{segment_id}")
def delete_segment(episode_id: int, segment_id: int,
                   db: Session = Depends(get_db)) -> dict:
    seg = db.get(models.EpisodeSegment, segment_id)
    if seg is None or seg.episode_id != episode_id:
        raise HTTPException(status_code=404, detail="segment not found")
    db.delete(seg)
    db.flush()
    _resequence(db, episode_id)
    db.commit()
    ep = db.get(models.Episode, episode_id)
    assert ep is not None
    return _detail(db, ep)


@router.post("/episodes/{episode_id}/segments/{segment_id}/duplicate")
def duplicate_segment(episode_id: int, segment_id: int,
                      db: Session = Depends(get_db)) -> dict:
    seg = db.get(models.EpisodeSegment, segment_id)
    if seg is None or seg.episode_id != episode_id:
        raise HTTPException(status_code=404, detail="segment not found")
    clone = models.EpisodeSegment(
        episode_id=episode_id, moment_id=seg.moment_id,
        sequence=seg.sequence, duration=seg.duration,
        transition_type=seg.transition_type,
        commentary_text=seg.commentary_text, context_text=seg.context_text,
    )
    db.add(clone)
    db.flush()
    _resequence(db, episode_id)
    db.commit()
    ep = db.get(models.Episode, episode_id)
    assert ep is not None
    return _detail(db, ep)


@router.post("/episodes/{episode_id}/rebuild")
def rebuild_episode(episode_id: int, payload: RebuildRequest,
                    db: Session = Depends(get_db)) -> dict:
    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    current = {
        s.id for s in db.query(models.EpisodeSegment)
        .filter_by(episode_id=episode_id).all()
    }
    if set(payload.segment_ids) != current:
        raise HTTPException(
            status_code=400,
            detail="segment_ids must contain exactly the episode's segments",
        )
    for idx, sid in enumerate(payload.segment_ids):
        db.get(models.EpisodeSegment, sid).sequence = idx  # type: ignore[union-attr]
    db.commit()
    return _detail(db, ep)
