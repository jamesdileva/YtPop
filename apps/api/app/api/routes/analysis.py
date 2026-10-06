"""Media analysis routes (S4): probe-only analyze with rights-basis gate."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.media_ingestion import IngestionError, probe_source

log = structlog.get_logger()
router = APIRouter()


class AnalyzeRequest(BaseModel):
    media_path: str = Field(min_length=1, max_length=500)
    rights_basis: str = Field(min_length=1, max_length=32)


@router.post("/sources/{source_id}/analyze")
def analyze_source(
    source_id: int, payload: AnalyzeRequest, db: Session = Depends(get_db)
) -> dict:
    try:
        summary = probe_source(
            db, source_id, payload.media_path, payload.rights_basis
        )
    except IngestionError as e:
        msg = str(e)
        code = 404 if "source not found" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from e
    db.commit()
    log.info("source_analyzed", source_id=source_id, asset_id=summary["asset_id"])
    return summary
