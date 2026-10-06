"""Discovery domain (S3): upsert + snapshots, velocity, ranking, quota guard.

S3 ranks by observed metadata only — topic clustering lands in S11.
All functions are deterministic and DB-backed so tests need no network.
"""

import math
import structlog
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models

log = structlog.get_logger()


# --- trend scoring -----------------------------------------------------------

def compute_trend_score(
    views: int, likes: int, comments: int, velocity_per_hour: float
) -> float:
    """Deterministic S3 score: log-scale popularity + engagement + velocity."""
    popularity = math.log10(max(views, 0) + 1) * 10  # 0..~90
    engagement_rate = (likes + comments) / max(views, 1)
    engagement = min(engagement_rate * 100, 20.0)  # capped
    velocity = min(max(velocity_per_hour, 0.0) / 1000.0 * 10, 30.0)  # capped
    return round(popularity + engagement + velocity, 3)


# --- snapshots + velocity -----------------------------------------------------

def record_snapshot(
    db: Session,
    source_id: int,
    views: int,
    likes: int,
    comments: int,
    taken_at: datetime | None = None,
) -> models.SourceSnapshot:
    snap = models.SourceSnapshot(
        source_id=source_id,
        view_count=views,
        like_count=likes,
        comment_count=comments,
        taken_at=taken_at or datetime.now(timezone.utc),
    )
    db.add(snap)
    db.flush()
    return snap


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_velocity(db: Session, source_id: int) -> float:
    """Views/hour between earliest and latest snapshot (0.0 if <2 snapshots)."""
    snaps = (
        db.execute(
            select(models.SourceSnapshot)
            .where(models.SourceSnapshot.source_id == source_id)
            .order_by(models.SourceSnapshot.taken_at.asc())
        )
        .scalars()
        .all()
    )
    if len(snaps) < 2:
        return 0.0
    first, last = snaps[0], snaps[-1]
    hours = (_as_utc(last.taken_at) - _as_utc(first.taken_at)).total_seconds() / 3600
    if hours <= 0:
        return 0.0
    return (last.view_count - first.view_count) / hours


# --- upsert -------------------------------------------------------------------

def upsert_source(db: Session, item: dict) -> tuple[models.Source, bool]:
    """Insert or refresh a Source from normalized adapter output + snapshot.

    Returns (source, created). Always writes a snapshot row so velocity can
    be computed after the second observation.
    """
    existing = db.execute(
        select(models.Source).where(
            models.Source.provider == item.get("provider", "youtube"),
            models.Source.external_id == item.get("external_id", ""),
        )
    ).scalar_one_or_none()
    if existing is None:
        row = models.Source(
            provider=item.get("provider", "youtube"),
            external_id=item.get("external_id", ""),
            url=item.get("url", ""),
            title=item.get("title", ""),
            channel_id=item.get("channel_id", ""),
            channel_name=item.get("channel_name", ""),
            category=item.get("category", ""),
            description=item.get("description", "")[:2000],
            thumbnail_url=item.get("thumbnail_url", ""),
            duration=float(item.get("duration", 0.0) or 0.0),
            view_count=int(item.get("view_count", 0) or 0),
            like_count=int(item.get("like_count", 0) or 0),
            comment_count=int(item.get("comment_count", 0) or 0),
            last_checked_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.flush()
        created = True
    else:
        row = existing
        for field in (
            "url", "title", "channel_id", "channel_name", "category",
            "description", "thumbnail_url",
        ):
            if item.get(field):
                setattr(row, field, item[field][:2000] if field == "description" else item[field])
        row.duration = float(item.get("duration", row.duration) or 0.0)
        row.view_count = int(item.get("view_count", 0) or 0)
        row.like_count = int(item.get("like_count", 0) or 0)
        row.comment_count = int(item.get("comment_count", 0) or 0)
        row.last_checked_at = datetime.now(timezone.utc)
        created = False
    record_snapshot(
        db, row.id, row.view_count, row.like_count, row.comment_count
    )
    row.trend_score = compute_trend_score(
        row.view_count, row.like_count, row.comment_count,
        compute_velocity(db, row.id),
    )
    db.flush()
    log.info(
        "source_upserted", source_id=row.id, created=created,
        views=row.view_count, score=row.trend_score,
    )
    return row, created


# --- quota guard ---------------------------------------------------------------

def quota_used_today(db: Session) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    total = db.execute(
        select(func.coalesce(func.sum(models.DiscoveryRun.units_consumed), 0)).where(
            func.date(models.DiscoveryRun.created_at) == today
        )
    ).scalar_one()
    return int(total or 0)


def check_quota(db: Session, units_needed: int, daily_budget: int) -> None:
    """Raise QuotaExceeded when today's usage + need would exceed budget."""
    used = quota_used_today(db)
    if used + units_needed > daily_budget:
        raise QuotaExceeded(
            f"quota guard: used {used} + need {units_needed} > budget {daily_budget}"
        )


class QuotaExceeded(RuntimeError):
    pass


def record_run(
    db: Session, run_type: str, region: str, category: str,
    units: int, source_count: int,
) -> models.DiscoveryRun:
    run = models.DiscoveryRun(
        run_type=run_type, region=region, category=category,
        units_consumed=units, source_count=source_count,
    )
    db.add(run)
    db.flush()
    return run


# --- trending sections ----------------------------------------------------------

def _brief(row: models.Source, velocity: float) -> dict:
    return {
        "id": row.id,
        "external_id": row.external_id,
        "title": row.title,
        "channel_name": row.channel_name,
        "category": row.category,
        "view_count": row.view_count,
        "trend_score": row.trend_score,
        "velocity_per_hour": round(velocity, 2),
    }


def trending_sections(db: Session, limit: int = 10) -> dict:
    """Four dashboard sections from DB observations (no clustering until S11)."""
    rows = db.execute(select(models.Source)).scalars().all()
    scored = [(r, compute_velocity(db, r.id)) for r in rows]
    day_ago = datetime.now(timezone.utc).timestamp() - 86400

    def _ts(row: models.Source) -> float:
        dt = row.discovered_at
        if dt is None:
            return 0.0
        return _as_utc(dt).timestamp()

    trending_now = sorted(scored, key=lambda p: p[0].view_count, reverse=True)[:limit]
    recent = [p for p in scored if _ts(p[0]) >= day_ago]
    recently_rising = sorted(recent, key=lambda p: p[1], reverse=True)[:limit]
    fastest_growing = sorted(scored, key=lambda p: p[1], reverse=True)[:limit]
    cats: dict[str, int] = {}
    for r in rows:
        cats[r.category or "uncategorized"] = cats.get(r.category or "uncategorized", 0) + 1
    top_categories = sorted(
        [{"category": k, "count": v} for k, v in cats.items()],
        key=lambda c: c["count"], reverse=True,
    )[:limit]
    return {
        "trending_now": [_brief(r, v) for r, v in trending_now],
        "recently_rising": [_brief(r, v) for r, v in recently_rising],
        "fastest_growing": [_brief(r, v) for r, v in fastest_growing],
        "top_categories": top_categories,
    }
