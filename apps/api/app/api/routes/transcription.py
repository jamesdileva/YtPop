"""Transcription routes (S5): sync transcribe + transcript read."""

import json
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.domain.analysis import service as analysis
from app.services.whisper_service import TranscriptionError, WhisperService

log = structlog.get_logger()
router = APIRouter()


def get_whisper_service() -> WhisperService:
    return WhisperService(
        settings.whisper_model, settings.whisper_device,
        settings.whisper_compute_type,
    )


class TranscribeRequest(BaseModel):
    model: str = Field(default="", max_length=64)
    language: str = Field(default="", max_length=16)
    force: bool = False


@router.post("/sources/{source_id}/transcribe")
def transcribe(
    source_id: int, payload: TranscribeRequest,
    db: Session = Depends(get_db),
    whisper: WhisperService = Depends(get_whisper_service),
) -> dict:
    try:
        svc = whisper
        if payload.model:
            svc = WhisperService(
                payload.model, settings.whisper_device,
                settings.whisper_compute_type,
            )
        summary = analysis.transcribe_source(
            db, source_id,
            model_name=payload.model or None,
            language=payload.language or None,
            force=payload.force, whisper=svc,
        )
    except TranscriptionError as e:
        msg = str(e)
        code = 404 if "source not found" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from e
    db.commit()
    log.info("source_transcribed", source_id=source_id,
             transcript_id=summary["transcript_id"])
    return summary


@router.get("/sources/{source_id}/transcript")
def get_transcript(source_id: int, db: Session = Depends(get_db)) -> dict:
    from app.db import models

    row = (
        db.query(models.Transcript)
        .filter_by(source_id=source_id)
        .order_by(models.Transcript.id.desc())
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="transcript not found")
    return {
        "id": row.id, "source_id": row.source_id,
        "language": row.language, "model": row.model,
        "text": row.text, "segments": json.loads(row.segments_json),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
