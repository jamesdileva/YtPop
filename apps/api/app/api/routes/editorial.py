"""Editorial routes (S10): AI-planned episode assembly."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes import episodes as episode_routes
from app.config import settings
from app.db import models
from app.db.database import get_db
from app.domain.editorial import service as editorial
from app.services.ollama_service import OllamaService, model_for

log = structlog.get_logger()
router = APIRouter()


def get_editorial_service() -> editorial.EditorialService:
    return editorial.EditorialService(
        OllamaService(model=model_for("editor"),
                      host=settings.ollama_host))


class GenerateRequest(BaseModel):
    moment_ids: list[int] = Field(default_factory=list)
    target_duration: float = Field(default=1200.0, gt=0)
    format: str = Field(default="daily_highlights", max_length=64)
    trend: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=64)


@router.post("/episodes/{episode_id}/generate")
def generate_episode(episode_id: int, payload: GenerateRequest,
                     db: Session = Depends(get_db),
                     svc: editorial.EditorialService = Depends(
                         get_editorial_service),
) -> dict:
    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if payload.model:
        svc = editorial.EditorialService(
            OllamaService(model=payload.model, host=settings.ollama_host))
    moments = (
        db.query(models.Moment)
        .filter(models.Moment.status == "APPROVED").all()
    )
    if payload.moment_ids:
        wanted = set(payload.moment_ids)
        moments = [m for m in moments if m.id in wanted]
    if not moments:
        raise HTTPException(
            status_code=400, detail="no APPROVED candidate moments")
    sources = [{
        "id": s.id, "title": s.title, "channel_name": s.channel_name,
    } for s in db.query(models.Source).all()]
    try:
        plan, meta = svc.plan(
            trend=payload.trend, sources=sources, moments=moments,
            target_duration=payload.target_duration, format=payload.format)
        applied = editorial.apply_plan(db, episode_id, plan)
    except editorial.EditorialError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    log.info("episode_generated", episode_id=episode_id,
             title=plan.title, repairs=meta["repairs"])
    return {
        "plan": plan.model_dump(), "meta": meta, "applied": applied,
        "episode": episode_routes._detail(db, ep),
    }
