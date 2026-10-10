"""Scene routes (D10): detect hard cuts + read them back."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.domain.analysis import scenes
from app.services import scene_service

log = structlog.get_logger()
router = APIRouter()


class DetectScenesRequest(BaseModel):
    media_path: str = Field(min_length=1, max_length=500)
    threshold: float = Field(default=0.35, ge=0.0, le=1.0)


@router.post("/sources/{source_id}/detect-scenes")
def detect(source_id: int, payload: DetectScenesRequest,
           db: Session = Depends(get_db)) -> dict:
    try:
        result = scenes.detect_and_store(db, source_id, payload.media_path,
                                        cfg={"threshold": payload.threshold})
    except scene_service.SceneError as e:
        msg = str(e)
        code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from e
    db.commit()
    return result


@router.get("/sources/{source_id}/scenes")
def list_scenes(source_id: int, db: Session = Depends(get_db)) -> dict:
    return scenes.list_scenes(db, source_id)
