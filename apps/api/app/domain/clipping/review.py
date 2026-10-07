"""Clip review (S7): trim/approve/reject with feedback capture + previews."""

import structlog
from pathlib import Path
from sqlalchemy.orm import Session

from app.db import models
from app.domain.clipping.service import ClipError
from app.services import ffmpeg_service as ff

log = structlog.get_logger()

REVIEW_STATUSES = frozenset({"CANDIDATE", "APPROVED", "REJECTED"})


def review_moment(
    db: Session, moment_id: int, status: str | None = None,
    start_time: float | None = None, end_time: float | None = None,
    notes: str | None = None, category: str | None = None,
    is_best: bool | None = None, reason: str = "",
) -> models.Moment:
    row = db.get(models.Moment, moment_id)
    if row is None:
        raise ClipError(f"moment not found: {moment_id}")
    original = (float(row.start_time), float(row.end_time))
    new_start = float(start_time) if start_time is not None else original[0]
    new_end = float(end_time) if end_time is not None else original[1]
    if not (new_start >= 0 and new_end > new_start):
        raise ClipError(
            f"invalid trim: need 0 <= start < end, got {new_start}/{new_end}"
        )
    if status is not None and status not in REVIEW_STATUSES:
        raise ClipError(
            f"invalid status {status!r}, one of {sorted(REVIEW_STATUSES)}"
        )
    trimmed = (new_start, new_end) != original
    if status is not None:
        row.status = status
        decision = status
    elif trimmed:
        decision = "TRIMMED"
    else:
        decision = "NOTED"
    row.start_time, row.end_time = new_start, new_end
    if notes is not None:
        row.notes = notes
    if category is not None:
        row.category = category
    if is_best is not None:
        row.is_best = bool(is_best)
    db.add(models.MomentFeedback(
        moment_id=row.id, decision=decision, reason=reason,
        original_start=original[0], original_end=original[1],
        adjusted_start=new_start, adjusted_end=new_end,
    ))
    db.flush()
    log.info("moment_reviewed", moment_id=row.id, decision=decision,
             trimmed=trimmed)
    return row


def _source_media(db: Session, source_id: int) -> Path:
    for kind in ("normalized", "raw"):
        asset = (
            db.query(models.MediaAsset)
            .filter_by(source_id=source_id, kind=kind)
            .order_by(models.MediaAsset.id.desc())
            .first()
        )
        if asset is not None and Path(asset.path).is_file():
            return Path(asset.path)
    raise ClipError(f"source {source_id} has no playable media — ingest first")


def build_preview(
    db: Session, moment_id: int, force: bool = False,
    roots: list[Path] | None = None,
) -> dict:
    row = db.get(models.Moment, moment_id)
    if row is None:
        raise ClipError(f"moment not found: {moment_id}")
    base = (roots or [ff.repo_data_dir()])[0]
    out = ff.resolve_data_path(Path("clips") / f"{moment_id}.mp4", [base])
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file() and not force:
        return {"moment_id": moment_id, "path": str(out),
                "duration": round(row.end_time - row.start_time, 3),
                "cached": True}
    src = _source_media(db, row.source_id)
    duration = round(row.end_time - row.start_time, 3)
    if duration <= 0:
        raise ClipError("moment has zero duration")
    try:
        ff.run_cmd("ffmpeg", [
            "-y", "-ss", str(row.start_time), "-i", str(src),
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-c:a", "aac", str(out),
        ])
    except (ff.FFmpegError, ff.PathTraversalError) as e:
        raise ClipError(str(e)) from e
    db.add(models.MediaAsset(
        source_id=row.source_id, kind="preview", path=str(out),
        duration=duration, codec="h264",
    ))
    db.flush()
    log.info("preview_built", moment_id=moment_id, duration=duration)
    return {"moment_id": moment_id, "path": str(out),
            "duration": duration, "cached": False}
