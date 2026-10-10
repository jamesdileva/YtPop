"""Ranker routes (D13): cadence status + manual retrain trigger."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.domain.clipping import retraining

log = structlog.get_logger()
router = APIRouter()


class RetrainRequest(BaseModel):
    force: bool = False


@router.get("/ranker/status")
def ranker_status(db: Session = Depends(get_db)) -> dict:
    return retraining.state(db)


@router.post("/ranker/retrain")
def retrain_ranker(payload: RetrainRequest,
                   db: Session = Depends(get_db)) -> dict:
    try:
        return retraining.maybe_retrain(db, force=payload.force)
    except retraining.RetrainError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
