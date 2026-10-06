"""Media ingestion (S4): probe → verify → normalize/audio/thumb + DB linkage.

Only material with an explicit permitted basis is accepted:
USER_OWNED, LICENSED, CREATIVE_COMMONS, PUBLIC_DOMAIN.
Arbitrary YouTube downloading is NOT part of this flow (see agents.md).
"""

import structlog
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session

from app.db import models
from app.services import ffmpeg_service as ff

log = structlog.get_logger()

PERMITTED_BASES = frozenset({
    "USER_OWNED", "LICENSED", "CREATIVE_COMMONS", "PUBLIC_DOMAIN",
})


class IngestionError(RuntimeError):
    pass


def check_basis(basis: str) -> str:
    normalized = (basis or "").upper()
    if normalized not in PERMITTED_BASES:
        raise IngestionError(
            f"rights basis required, one of {sorted(PERMITTED_BASES)}; got {basis!r}"
        )
    return normalized


def verify_media(info: dict) -> dict:
    """Gate: video stream + duration>0 + audio stream required."""
    errors: list[str] = []
    if not info.get("has_video"):
        errors.append("no video stream")
    if not info.get("duration") or float(info["duration"]) <= 0:
        errors.append("duration missing or zero")
    if not info.get("has_audio"):
        errors.append("no audio stream")
    return {"ok": not errors, "errors": errors}


def _record_asset(
    db: Session, source_id: int, kind: str, path: Path,
    info: dict | None = None,
) -> models.MediaAsset:
    asset = models.MediaAsset(
        source_id=source_id, kind=kind, path=str(path),
        width=int((info or {}).get("width", 0) or 0),
        height=int((info or {}).get("height", 0) or 0),
        duration=float((info or {}).get("duration", 0.0) or 0.0),
        codec=str((info or {}).get("vcodec" if kind != "audio" else "acodec", "")),
    )
    db.add(asset)
    db.flush()
    return asset


def _record_rights(db: Session, source_id: int, basis: str) -> models.RightsRecord:
    existing = (
        db.query(models.RightsRecord)
        .filter_by(source_id=source_id).one_or_none()
    )
    if existing is None:
        row = models.RightsRecord(
            source_id=source_id, status=basis, basis=basis,
            notes="S4 ingestion basis (human-supplied)",
            verified_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.flush()
        return row
    existing.status = basis
    existing.basis = basis
    existing.verified_at = datetime.now(timezone.utc)
    db.flush()
    return existing


def probe_source(
    db: Session, source_id: int, media_path: str | Path,
    rights_basis: str, roots: list[Path] | None = None,
) -> dict:
    """Probe-only analyze: validate basis → probe → verify → record raw asset."""
    basis = check_basis(rights_basis)
    row = db.get(models.Source, source_id)
    if row is None:
        raise IngestionError(f"source not found: {source_id}")
    try:
        info = ff.probe(media_path, roots)
    except (ff.FFmpegError, ff.PathTraversalError) as e:
        raise IngestionError(str(e)) from e
    verdict = verify_media(info)
    if not verdict["ok"]:
        raise IngestionError(f"media verification failed: {verdict['errors']}")
    asset = _record_asset(db, source_id, "raw", Path(info["path"]), info)
    _record_rights(db, source_id, basis)
    row.duration = info["duration"]
    row.last_checked_at = datetime.now(timezone.utc)
    db.flush()
    log.info(
        "media_probed", source_id=source_id, asset_id=asset.id,
        duration=info["duration"], basis=basis,
    )
    return {"source_id": source_id, "asset_id": asset.id, **info}


def ingest_source(
    db: Session, source_id: int, media_path: str | Path,
    rights_basis: str, roots: list[Path] | None = None,
) -> dict:
    """Full pipeline: probe → normalize → audio → thumb, all assets recorded."""
    summary = probe_source(db, source_id, media_path, rights_basis, roots)
    base = (roots or [ff.repo_data_dir()])[0]
    src = Path(summary["path"])
    norm_rel = Path("media") / str(source_id) / "normalized.mp4"
    audio_rel = Path("media") / str(source_id) / "audio_16k.wav"
    thumb_rel = Path("thumbnails") / f"{source_id}.jpg"
    try:
        norm = ff.normalize(src, base / norm_rel, roots=[base])
        norm_info = ff.probe(norm, [base])
        audio = ff.extract_audio(src, base / audio_rel, roots=[base])
        thumb = ff.extract_thumbnail(src, base / thumb_rel, roots=[base])
    except (ff.FFmpegError, ff.PathTraversalError) as e:
        raise IngestionError(str(e)) from e
    _record_asset(db, source_id, "normalized", norm, norm_info)
    _record_asset(db, source_id, "audio", audio, {"acodec": "pcm_s16le"})
    _record_asset(db, source_id, "thumbnail", thumb)
    db.flush()
    log.info("media_ingested", source_id=source_id, duration=summary["duration"])
    return {
        **summary,
        "normalized": str(norm), "audio": str(audio), "thumbnail": str(thumb),
    }
