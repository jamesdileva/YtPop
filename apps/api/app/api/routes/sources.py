import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db

log = structlog.get_logger()
router = APIRouter()


class SourceCreate(BaseModel):
    provider: str = Field(default="youtube", max_length=32)
    external_id: str = Field(max_length=128)
    url: str = ""
    title: str = ""
    channel_id: str = ""
    channel_name: str = ""
    category: str = ""


class SourceRead(BaseModel):
    id: int
    provider: str
    external_id: str
    url: str
    title: str
    channel_id: str
    channel_name: str
    category: str
    status: str

    model_config = {"from_attributes": True}


@router.post("/sources", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)) -> SourceRead:
    row = models.Source(
        provider=payload.provider,
        external_id=payload.external_id,
        url=payload.url,
        title=payload.title,
        channel_id=payload.channel_id,
        channel_name=payload.channel_name,
        category=payload.category,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log.info("source_created", source_id=row.id, external_id=row.external_id)
    return SourceRead.model_validate(row)


@router.get("/sources", response_model=list[SourceRead])
def list_sources(limit: int = 50, db: Session = Depends(get_db)) -> list[SourceRead]:
    rows = db.execute(select(models.Source).limit(limit)).scalars().all()
    return [SourceRead.model_validate(r) for r in rows]


@router.get("/sources/{source_id}", response_model=SourceRead)
def get_source(source_id: int, db: Session = Depends(get_db)) -> SourceRead:
    row = db.get(models.Source, source_id)
    if row is None:
        raise HTTPException(status_code=404, detail="source not found")
    return SourceRead.model_validate(row)
