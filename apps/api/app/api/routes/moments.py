"""Moment routes (S6): find candidates + ranked reads."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.db.database import get_db
from app.domain.clipping import service as clipping

log = structlog.get_logger()
router = APIRouter()


def get_embedder():
    if not settings.clip_embeddings:
        return None
    return clipping.Embedder().encode


class FindMomentsRequest(BaseModel):
    top_k: int = Field(default=10, ge=1, le=50)


@router.post("/sources/{source_id}/find-moments")
def find_moments(
    source_id: int, payload: FindMomentsRequest,
    db: Session = Depends(get_db),
    embed_fn=Depends(get_embedder),
) -> dict:
    try:
        summary = clipping.find_moments(
            db, source_id, top_k=payload.top_k, embed_fn=embed_fn,
        )
    except clipping.ClipError as e:
        msg = str(e)
        code = 404 if "source not found" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from e
    db.commit()
    log.info("moments_endpoint", source_id=source_id, total=summary["total"])
    return summary


def _brief(row: models.Moment) -> dict:
    return {
        "id": row.id, "source_id": row.source_id,
        "start_time": row.start_time, "end_time": row.end_time,
        "transcript_excerpt": row.transcript_excerpt,
        "moment_type": row.moment_type,
        "semantic_score": row.semantic_score,
        "emotion_score": row.emotion_score,
        "novelty_score": row.novelty_score,
        "editorial_score": row.editorial_score,
        "final_score": row.final_score, "status": row.status,
    }


@router.get("/moments")
def list_moments(
    source_id: int | None = None, limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict]:
    q = db.query(models.Moment).order_by(models.Moment.final_score.desc())
    if source_id is not None:
        q = q.filter_by(source_id=source_id)
    return [_brief(r) for r in q.limit(max(limit, 1)).all()]


@router.get("/moments/{moment_id}")
def get_moment(moment_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(models.Moment, moment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="moment not found")
    return _brief(row)
