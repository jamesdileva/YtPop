"""Daily-episode orchestrator (S13): stages → draft episode + render.

Runs the full chain on local material: scores → cluster → analysis →
rights filter → editorial plan → timeline → render → QA. Discovery is a
stage too but skips gracefully without a YouTube key. Each stage goes
through the job queue (full traceability); any failure aborts with the
stage name and error.
"""

import structlog
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session

from app.db import models
from app.domain.rights import service as rights_svc
from app.workers import handlers, queue as q

log = structlog.get_logger()


class PipelineError(RuntimeError):
    pass


def _run_stage(db: Session, ctx: handlers.Ctx, job_type: str,
               payload: dict, priority: int = 30) -> dict:
    job = q.enqueue(db, job_type, payload, priority)
    db.commit()
    try:
        result = handlers.run_job(db, job.id, ctx)
    except q.JobError as e:
        raise PipelineError(f"stage {job_type} failed: {e}") from e
    return result


def run_daily_episode(db: Session, ctx: handlers.Ctx | None = None,
                      trend: str = "", format: str = "daily_highlights",
                      preset: str = "preview_720p", model: str = "",
                      roots: list[Path] | None = None) -> dict:
    ctx = ctx or handlers.Ctx(roots=roots)
    stages: list[dict] = []

    def stage(name: str, job_type: str, payload: dict,
              priority: int = 30) -> dict:
        try:
            result = _run_stage(db, ctx, job_type, payload, priority)
        except PipelineError as e:
            stages.append({"stage": name, "status": "FAILED",
                           "detail": str(e)[:500]})
            raise
        stages.append({"stage": name, "status": "COMPLETED",
                       "detail": str(result)[:500]})
        return result

    # 1-2. scores + clustering (topic = top trend unless pinned)
    stage("refresh_scores", "REFRESH_SCORES", {})
    clustered = stage("cluster", "CLUSTER", {"region": "US"})
    trends = sorted(clustered.get("trends", []),
                    key=lambda t: t["score"], reverse=True)
    if trend:
        picked = next((t for t in trends
                       if trend.lower() in t["topic"].lower()), None)
        if picked is None:
            raise PipelineError(f"no trend matching {trend!r}")
    elif trends:
        picked = trends[0]
    else:
        raise PipelineError("no trends — discover sources first")
    topic = picked["topic"]
    member_ids = sorted(
        r.source_id for r in db.query(models.TrendSource)
        .filter_by(trend_id=picked["trend_id"]).all())

    # 3. analysis backlog for member sources
    from app.domain.discovery import service as discovery

    for sid in member_ids:
        has_tr = db.query(models.Transcript).filter_by(
            source_id=sid).count() > 0
        if not has_tr:
            vel = discovery.compute_velocity(db, sid)
            stage(f"transcribe:{sid}", "TRANSCRIBE", {"source_id": sid},
                  q.priority_for_velocity(vel))
        has_mo = db.query(models.Moment).filter_by(
            source_id=sid).count() > 0
        if not has_mo:
            stage(f"moments:{sid}", "FIND_MOMENTS",
                  {"source_id": sid, "top_k": 10})

    # 4. rights filter (approved only — research material stays local)
    approved = (db.query(models.Moment)
                .filter(models.Moment.source_id.in_(member_ids),
                        models.Moment.status == "APPROVED").all())
    if not approved:
        raise PipelineError(
            "no APPROVED moments in trend — review candidates first")

    # 5-6. episode + editorial plan + render
    ep = models.Episode(title=f"Daily — {topic}", target_duration=1200.0)
    db.add(ep)
    db.commit()
    stage("generate", "GENERATE",
          {"episode_id": ep.id, "trend": topic, "format": format,
           "model": model})
    rendered = stage("render", "RENDER",
                     {"episode_id": ep.id, "preset": preset})
    if not rendered.get("qa_ok"):
        raise PipelineError("render QA failed")

    # 7. publish pre-check (informational — demo mode blocks by default)
    from app.config import settings

    verdict = rights_svc.episode_verdict(db, ep.id, settings.demo_mode)
    log.info("daily_episode_done", episode_id=ep.id, trend=topic,
             render_id=rendered.get("render_id"),
             publishable=verdict["publishable"])
    return {
        "episode_id": ep.id,
        "render_id": rendered.get("render_id"),
        "trend": topic,
        "stages": stages,
        "publishable": verdict["publishable"],
        "blocked": verdict["blocked"],
        "review": "episode is DRAFT — review in the Episodes page",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
