"""Transcription orchestration (S5): wav → whisper → DB + json artifact.

Idempotent: re-running without changes skips when the wav sha matches the
stored transcript (unless force=True). A TRANSCRIBE job row is recorded for
direct calls so S13 history exists — but not when the queue already owns a
row for this work (D3).
"""

import hashlib
import json
import structlog
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.services import ffmpeg_service as ff
from app.services.whisper_service import TranscriptionError, WhisperService

log = structlog.get_logger()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _wav_for_source(
    db: Session, source_id: int, roots: list[Path] | None
) -> Path:
    audio = (
        db.query(models.MediaAsset)
        .filter_by(source_id=source_id, kind="audio")
        .order_by(models.MediaAsset.id.desc())
        .first()
    )
    if audio is not None and Path(audio.path).is_file():
        return Path(audio.path)
    raw = (
        db.query(models.MediaAsset)
        .filter_by(source_id=source_id, kind="raw")
        .order_by(models.MediaAsset.id.desc())
        .first()
    )
    if raw is None or not Path(raw.path).is_file():
        raise TranscriptionError(
            f"source {source_id} has no audio/raw asset — ingest first"
        )
    base = (roots or [ff.repo_data_dir()])[0]
    out = base / "media" / str(source_id) / "audio_16k.wav"
    ff.extract_audio(raw.path, out, [base])
    asset = models.MediaAsset(
        source_id=source_id, kind="audio", path=str(out), codec="pcm_s16le"
    )
    db.add(asset)
    db.flush()
    return out


def _write_artifact(
    source_id: int, transcript_id: int, result: dict,
    roots: list[Path] | None,
) -> Path:
    base = (roots or [ff.repo_data_dir()])[0]
    rel = Path("transcripts") / f"{source_id}.json"
    out = ff.resolve_data_path(rel, [base])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "source_id": source_id,
        "transcript_id": transcript_id,
        "language": result["language"],
        "model": result["model"],
        "segments": result["segments"],
    }, indent=2), encoding="utf-8")
    return out


def transcribe_source(
    db: Session, source_id: int,
    model_name: str | None = None, language: str | None = None,
    force: bool = False, roots: list[Path] | None = None,
    whisper: WhisperService | None = None,
) -> dict:
    row = db.get(models.Source, source_id)
    if row is None:
        raise TranscriptionError(f"source not found: {source_id}")
    wav = _wav_for_source(db, source_id, roots)
    digest = _sha256(wav)
    existing = (
        db.query(models.Transcript)
        .filter_by(source_id=source_id, audio_sha256=digest)
        .order_by(models.Transcript.id.desc())
        .first()
    )
    if existing is not None and not force:
        log.info("transcript_skip", source_id=source_id,
                 transcript_id=existing.id)
        return {
            "source_id": source_id, "transcript_id": existing.id,
            "language": existing.language, "model": existing.model,
            "segments": len(json.loads(existing.segments_json)),
            "skipped": True,
        }
    svc = whisper or WhisperService(
        model_name or settings.whisper_model,
        settings.whisper_device, settings.whisper_compute_type,
    )
    try:
        result = svc.transcribe(wav, language=language)
    except Exception as e:
        raise TranscriptionError(str(e)) from e
    result["model"] = svc.model_name if isinstance(svc, WhisperService) else "test"
    tr = models.Transcript(
        source_id=source_id, language=result["language"],
        model=result["model"], text=result["text"],
        segments_json=json.dumps(result["segments"]),
        audio_sha256=digest,
    )
    db.add(tr)
    db.flush()
    artifact = _write_artifact(source_id, tr.id, result, roots)
    # D3: the queue already owns the job row when this runs under a job
    from app.workers import context as ctxmod

    job_id: int | None = ctxmod.active_job_id()
    if job_id is None:
        job = models.Job(
            type="TRANSCRIBE", status="COMPLETED", priority=30,
            payload_json=json.dumps({"source_id": source_id,
                                     "model": result["model"]}),
            progress=1.0, attempts=1,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.flush()
        job_id = job.id
    log.info("transcribed", source_id=source_id, transcript_id=tr.id,
             segments=len(result["segments"]), job_id=job_id)
    return {
        "source_id": source_id, "transcript_id": tr.id,
        "language": result["language"], "model": result["model"],
        "segments": len(result["segments"]), "job_id": job_id,
        "artifact": str(artifact), "skipped": False,
    }
