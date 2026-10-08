"""Stage handlers (S13): each job type → existing S1–S12 services.

Handlers take (db, payload, ctx). ctx carries injectable backends so tests
run fully offline; production defaults wire the real services. Every
handler is idempotent (re-runs overwrite rather than duplicate).
"""

import structlog
from pathlib import Path
from sqlalchemy.orm import Session

from app.db import models
from app.domain.discovery import clustering
from app.domain.discovery import service as discovery
from app.workers import queue as q

log = structlog.get_logger()


class Ctx:
    """Injectable backends (None = production default)."""

    def __init__(self, youtube=None, whisper=None, embed_fn=None,
                 editorial=None, roots: list[Path] | None = None) -> None:
        self.youtube = youtube
        self.whisper = whisper
        self.embed_fn = embed_fn
        self.editorial = editorial
        self.roots = roots

    def youtube_service(self):
        if self.youtube is not None:
            return self.youtube
        from app.config import settings
        from app.services.youtube_service import YouTubeService

        return YouTubeService(api_key=settings.youtube_api_key)

    def whisper_service(self, model: str = ""):
        if self.whisper is not None:
            return self.whisper
        from app.config import settings
        from app.services.whisper_service import WhisperService

        return WhisperService(
            model or settings.whisper_model, settings.whisper_device,
            settings.whisper_compute_type)

    def embeddings(self):
        if self.embed_fn is not None:
            return self.embed_fn
        from app.config import settings

        if not settings.clip_embeddings:
            return None
        from app.domain.clipping.service import Embedder

        return Embedder().encode

    def editorial_service(self):
        if self.editorial is not None:
            return self.editorial
        from app.config import settings
        from app.domain.editorial.service import EditorialService
        from app.services.ollama_service import OllamaService, model_for

        return EditorialService(
            OllamaService(model=model_for("editor"),
                          host=settings.ollama_host))


def handle_refresh_scores(db: Session, payload: dict, ctx: Ctx) -> dict:
    rows = db.query(models.Source).all()
    for row in rows:
        row.trend_score = discovery.compute_trend_score(
            row.view_count, row.like_count, row.comment_count,
            discovery.compute_velocity(db, row.id))
    return {"updated": len(rows)}


def handle_cluster(db: Session, payload: dict, ctx: Ctx) -> dict:
    return clustering.cluster_trends(
        db, region=payload.get("region", "US"),
        category=payload.get("category", ""),
        threshold=payload.get("threshold", 0.55))


def handle_discover(db: Session, payload: dict, ctx: Ctx) -> dict:
    from app.services.youtube_service import COST_MOST_POPULAR

    from app.config import settings

    discovery.check_quota(
        db, COST_MOST_POPULAR, settings.youtube_quota_daily_budget)
    items, units = ctx.youtube_service().get_most_popular(
        region=payload.get("region", "US"),
        category_id=payload.get("category", ""),
        max_results=int(payload.get("max_results", 25)))
    imported = 0
    for item in items:
        _, created = discovery.upsert_source(db, item)
        imported += 1 if created else 0
    discovery.record_run(
        db, "most_popular", payload.get("region", "US"),
        payload.get("category", ""), units, len(items))
    return {"imported": imported, "seen": len(items), "units": units}


def _transcribe_one(db: Session, source_id: int, payload: dict,
                    ctx: Ctx) -> dict:
    from app.domain.analysis import service as analysis

    return analysis.transcribe_source(
        db, source_id, model_name=payload.get("model") or None,
        force=bool(payload.get("force", False)), roots=ctx.roots,
        whisper=ctx.whisper)


def handle_transcribe(db: Session, payload: dict, ctx: Ctx) -> dict:
    return _transcribe_one(db, int(payload["source_id"]), payload, ctx)


def handle_find_moments(db: Session, payload: dict, ctx: Ctx) -> dict:
    from app.domain.clipping import service as clipping

    return clipping.find_moments(
        db, int(payload["source_id"]),
        top_k=int(payload.get("top_k", 10)), embed_fn=ctx.embeddings())


def handle_drain_analysis(db: Session, payload: dict, ctx: Ctx) -> dict:
    """Continuous queue: oldest un-transcribed sources (by velocity)."""
    limit = int(payload.get("limit", 5))
    transcribed = {r.source_id for r in db.query(models.Transcript).all()}
    candidates = [s for s in db.query(models.Source).all()
                  if s.id not in transcribed]
    scored = sorted(
        ((discovery.compute_velocity(db, s.id), s) for s in candidates),
        reverse=True)[:limit]
    done, moments = [], 0
    for vel, src in scored:
        _transcribe_one(db, src.id, payload, ctx)
        done.append(src.id)
        from app.domain.clipping import service as clipping

        summary = clipping.find_moments(
            db, src.id, top_k=int(payload.get("top_k", 10)),
            embed_fn=ctx.embeddings())
        moments += summary["total"]
    return {"transcribed": done, "moments_total": moments}


def handle_generate(db: Session, payload: dict, ctx: Ctx) -> dict:
    from app.domain.editorial import service as editorial

    episode_id = int(payload["episode_id"])
    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise q.JobError(f"episode not found: {episode_id}")
    moments = (db.query(models.Moment)
               .filter(models.Moment.status == "APPROVED").all())
    wanted = payload.get("moment_ids")
    if wanted:
        wanted_set = set(wanted)
        moments = [m for m in moments if m.id in wanted_set]
    if not moments:
        raise q.JobError("no APPROVED candidate moments")
    if payload.get("model"):
        from app.config import settings
        from app.domain.editorial.service import EditorialService
        from app.services.ollama_service import OllamaService

        svc = EditorialService(
            OllamaService(model=payload["model"],
                          host=settings.ollama_host))
    else:
        svc = ctx.editorial_service()
    plan, meta = ctx.editorial_service().plan(
        trend=payload.get("trend", ""), sources=[],
        moments=moments,
        target_duration=float(payload.get("target_duration", 1200.0)),
        format=payload.get("format", "daily_highlights"))
    applied = editorial.apply_plan(
        db, episode_id, plan, roots=ctx.roots)
    return {"title": plan.title, "repairs": meta["repairs"], **applied}


def handle_render(db: Session, payload: dict, ctx: Ctx) -> dict:
    from app.domain.rendering import service as rendering

    summary = rendering.render_episode(
        db, int(payload["episode_id"]),
        preset_name=payload.get("preset", "preview_720p"),
        roots=ctx.roots)
    return {"render_id": summary["render_id"], "qa_ok": summary["qa"]["ok"]}


HANDLERS = {
    "REFRESH_SCORES": handle_refresh_scores,
    "CLUSTER": handle_cluster,
    "DISCOVER": handle_discover,
    "TRANSCRIBE": handle_transcribe,
    "FIND_MOMENTS": handle_find_moments,
    "DRAIN_ANALYSIS": handle_drain_analysis,
    "GENERATE": handle_generate,
    "RENDER": handle_render,
}


def run_job(db: Session, job_id: int, ctx: Ctx | None = None) -> dict:
    """Execute one QUEUED job synchronously (claim → run → complete/fail)."""
    ctx = ctx or Ctx()
    job = db.get(models.Job, job_id)
    if job is None:
        raise q.JobError(f"job not found: {job_id}")
    if job.status != "QUEUED":
        raise q.JobError(f"job {job_id} is {job.status}, not QUEUED")
    import json as _json

    job.status = "RUNNING"
    job.started_at = q._now()
    db.flush()
    handler = HANDLERS.get(job.type)
    if handler is None:
        q.fail(db, job, f"unknown job type {job.type!r}")
        db.commit()
        raise q.JobError(f"unknown job type {job.type!r}")
    try:
        result = handler(db, _json.loads(job.payload_json), ctx)
    except Exception as e:
        q.fail(db, job, f"{job.type} failed: {e}")
        db.commit()
        raise q.JobError(f"{job.type} failed: {e}") from e
    job.progress = 0.5
    db.flush()
    q.complete(db, job, result)
    db.commit()
    log.info("job_ran", job_id=job.id, type=job.type)
    return result
