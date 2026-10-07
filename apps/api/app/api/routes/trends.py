"""Discovery + trends routes (S3). Manual trigger only — no scheduler yet."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.db.database import get_db
from app.domain.discovery import clustering
from app.domain.discovery import service as discovery
from app.services.youtube_service import (
    COST_MOST_POPULAR,
    COST_SEARCH,
    YouTubeAPIError,
    YouTubeService,
)

log = structlog.get_logger()
router = APIRouter()


def get_youtube_service() -> YouTubeService:
    return YouTubeService(api_key=settings.youtube_api_key)


class DiscoverRequest(BaseModel):
    region: str = Field(default="US", max_length=8)
    category: str = Field(default="", max_length=64)
    max_results: int = Field(default=25, ge=1, le=50)


class SearchRequest(DiscoverRequest):
    query: str = Field(min_length=1, max_length=200)


@router.post("/sources/discover")
def discover_sources(
    payload: DiscoverRequest,
    db: Session = Depends(get_db),
    yt: YouTubeService = Depends(get_youtube_service),
) -> dict:
    try:
        discovery.check_quota(db, COST_MOST_POPULAR, settings.youtube_quota_daily_budget)
        items, units = yt.get_most_popular(
            region=payload.region,
            category_id=payload.category,
            max_results=payload.max_results,
        )
    except discovery.QuotaExceeded as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    except YouTubeAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    imported = 0
    for item in items:
        _, created = discovery.upsert_source(db, item)
        imported += 1 if created else 0
    discovery.record_run(
        db, "most_popular", payload.region, payload.category,
        units, len(items),
    )
    db.commit()
    log.info(
        "discover_done", run_type="most_popular", imported=imported,
        units=units, quota_used=discovery.quota_used_today(db),
    )
    return {
        "imported": imported, "seen": len(items), "units_consumed": units,
        "quota_used_today": discovery.quota_used_today(db),
    }


@router.post("/sources/search")
def search_sources(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    yt: YouTubeService = Depends(get_youtube_service),
) -> dict:
    try:
        discovery.check_quota(db, COST_SEARCH, settings.youtube_quota_daily_budget)
        items, units = yt.search_videos(
            query=payload.query, region=payload.region,
            max_results=payload.max_results,
        )
    except discovery.QuotaExceeded as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    except YouTubeAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    imported = 0
    for item in items:
        _, created = discovery.upsert_source(db, item)
        imported += 1 if created else 0
    discovery.record_run(
        db, "search", payload.region, payload.category, units, len(items)
    )
    db.commit()
    return {
        "imported": imported, "seen": len(items), "units_consumed": units,
        "quota_used_today": discovery.quota_used_today(db),
    }


@router.post("/trends/discover")
def refresh_trends(db: Session = Depends(get_db)) -> dict:
    """Recompute trend_score for all sources from latest snapshots (no API use)."""
    sources = db.query(models.Source).all()
    for row in sources:
        row.trend_score = discovery.compute_trend_score(
            row.view_count, row.like_count, row.comment_count,
            discovery.compute_velocity(db, row.id),
        )
    db.commit()
    return {"updated": len(sources), "sections": discovery.trending_sections(db)}


@router.get("/trends")
def get_trends(db: Session = Depends(get_db)) -> dict:
    return discovery.trending_sections(db)


@router.get("/trends/{trend_id}")
def get_trend(trend_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(models.TrendEvent, trend_id)
    if row is None:
        raise HTTPException(status_code=404, detail="trend not found")
    return {
        "id": row.id, "topic": row.topic, "description": row.description,
        "score": row.score, "velocity": row.velocity, "region": row.region,
        "category": row.category, "status": row.status,
    }


def get_cluster_llm():
    """Summarizer LLM override point (default None → keyword fallback)."""
    return None


class ClusterRequest(BaseModel):
    region: str = Field(default="US", max_length=8)
    category: str = Field(default="", max_length=64)
    threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    summarize: bool = False


@router.post("/trends/cluster")
def cluster_trends_endpoint(
    payload: ClusterRequest, db: Session = Depends(get_db),
    llm=Depends(get_cluster_llm),
) -> dict:
    if payload.summarize and llm is None:
        from app.services.ollama_service import OllamaService, model_for

        llm = OllamaService(model=model_for("summarizer"),
                            host=settings.ollama_host)
    try:
        return clustering.cluster_trends(
            db, region=payload.region, category=payload.category,
            threshold=payload.threshold, llm=llm,
        )
    except clustering.TrendError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/trend-events")
def list_trend_events(db: Session = Depends(get_db)) -> list[dict]:
    rows = (db.query(models.TrendEvent)
            .order_by(models.TrendEvent.score.desc()).all())
    out = []
    for row in rows:
        members = (db.query(models.TrendSource)
                   .filter_by(trend_id=row.id).all())
        out.append({
            "id": row.id, "topic": row.topic,
            "description": row.description, "score": row.score,
            "velocity": row.velocity, "region": row.region,
            "category": row.category, "status": row.status,
            "sources": len(members),
            "combined_views": sum(
                (db.get(models.Source, m.source_id).view_count
                 if db.get(models.Source, m.source_id) else 0)
                for m in members),
        })
    return out
