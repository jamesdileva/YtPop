"""Editorial overlay build (Phase 9 / D11) + read-back."""

import json
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.domain.editorial import overlays
from app.domain.editorial import service as editorial

log = structlog.get_logger()
router = APIRouter()


class BuildOverlaysRequest(BaseModel):
    plan: dict | None = Field(default=None, description="editorial plan JSON")
    target_duration: float = Field(default=1200.0, gt=0)
    format: str = Field(default="daily_highlights", max_length=64)
    trend: str = Field(default="", max_length=200)


class OverlayRecord(BaseModel):
    id: int
    episode_id: int
    kind: str
    timeline_at: float
    duration: float
    text: str
    asset_path: str | None = None
    moment_id: int | None = None
    source_id: int | None = None


class OverlayRead(BaseModel):
    episode_id: int
    title: str
    narration: list[tuple[float, str]]
    items: list[dict]


def get_editorial_svc():
    return editorial.EditorialService


@router.post("/episodes/{episode_id}/overlays")
def build_overlays(episode_id: int, payload: BuildOverlaysRequest,
                   db: Session = Depends(get_db)) -> dict:
    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if payload.plan:
        try:
            plan = editorial.EpisodePlan.model_validate(payload.plan)
        except Exception as e:
            raise HTTPException(status_code=400,
                                detail=f"invalid plan JSON: {e}") from e
    else:
        # fall back to the stored storyboard artifact from generate()
        from pathlib import Path

        from app.services import ffmpeg_service as ff

        artifact = ff.repo_data_dir() / "storyboards" / f"{episode_id}.json"
        if not artifact.is_file():
            raise HTTPException(
                status_code=400,
                detail="no plan supplied and no stored storyboard - run "
                       "POST /episodes/{id}/generate first")
        try:
            plan = editorial.EpisodePlan.model_validate(
                json.loads(artifact.read_text()))
        except Exception as e:
            raise HTTPException(status_code=400,
                                detail=f"stored plan invalid: {e}") from e
    try:
        result = overlays.build_overlays(db, episode_id, plan)
    except overlays.OverlayError as e:
        msg = str(e)
        code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from e
    db.commit()
    return result


@router.get("/episodes/{episode_id}/overlays", response_model=OverlayRead)
def get_overlays(episode_id: int, db: Session = Depends(get_db)) -> OverlayRead:
    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    from pathlib import Path

    from app.services import ffmpeg_service as ff

    artifact = ff.repo_data_dir() / "overlays" / f"{episode_id}.json"
    if not artifact.is_file():
        raise HTTPException(status_code=404, detail="no overlay pack yet")
    pack = json.loads(artifact.read_text())
    return OverlayRead(**pack)


@router.post("/overlays", response_model=OverlayRead)
def create_overlay(payload: OverlayRecord, db: Session = Depends(get_db)) -> OverlayRead:
    raise HTTPException(status_code=501,
                        detail="overlay packs are generated, not hand-written")
