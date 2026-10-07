"""Rights routes (S12): review workflow + publish blocker."""

import structlog
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.domain.rights import service as rights

log = structlog.get_logger()
router = APIRouter()


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"bad datetime {value!r}") from e


class ReviewRequest(BaseModel):
    note: str = Field(default="", max_length=2000)


class RightsPatch(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    basis: str | None = Field(default=None, max_length=64)
    owner: str | None = Field(default=None, max_length=256)
    license: str | None = Field(default=None, max_length=128)
    permission_reference: str | None = Field(default=None, max_length=2000)
    restrictions: str | None = Field(default=None, max_length=2000)
    territory: str | None = Field(default=None, max_length=64)
    commercial_allowed: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)
    reviewer: str | None = Field(default=None, max_length=128)
    expires_at: str | None = Field(default=None, max_length=64)


def _rights_error(e: rights.RightsError) -> HTTPException:
    msg = str(e)
    code = 404 if "not found" in msg else 400
    return HTTPException(status_code=code, detail=msg)


@router.get("/rights/{source_id}")
def get_rights(source_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return rights.get_rights(db, source_id)
    except rights.RightsError as e:
        raise _rights_error(e) from e


@router.post("/rights/{source_id}/review")
def request_review(source_id: int, payload: ReviewRequest,
                   db: Session = Depends(get_db)) -> dict:
    try:
        body = rights.request_review(db, source_id, note=payload.note)
    except rights.RightsError as e:
        raise _rights_error(e) from e
    db.commit()
    return body


@router.patch("/rights/{source_id}")
def patch_rights(source_id: int, payload: RightsPatch,
                 db: Session = Depends(get_db)) -> dict:
    fields = {k: v for k, v in payload.model_dump().items()
              if v is not None}
    if "expires_at" in fields:
        fields["expires_at"] = _parse_dt(fields["expires_at"])
    try:
        body = rights.update_rights(db, source_id, fields)
    except rights.RightsError as e:
        raise _rights_error(e) from e
    db.commit()
    log.info("rights_updated", source_id=source_id,
             status=body["status"])
    return body


@router.get("/rights/{source_id}/publish-check")
def publish_check(source_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return rights.publish_verdict(db, source_id, settings.demo_mode)
    except rights.RightsError as e:
        raise _rights_error(e) from e


@router.get("/episodes/{episode_id}/publish-check")
def episode_publish_check(episode_id: int,
                          db: Session = Depends(get_db)) -> dict:
    try:
        return rights.episode_verdict(db, episode_id, settings.demo_mode)
    except rights.RightsError as e:
        raise _rights_error(e) from e
