"""Render routes (S9): sync render + record reads + file serving."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.domain.rendering import service as rendering

log = structlog.get_logger()
router = APIRouter()


class RenderRequest(BaseModel):
    preset: str = Field(default="preview_720p", max_length=32)


def _brief(row: models.Render) -> dict:
    return {
        "id": row.id, "episode_id": row.episode_id, "preset": row.preset,
        "resolution": row.resolution, "fps": row.fps, "codec": row.codec,
        "path": row.path, "status": row.status, "error": row.error,
    }


@router.post("/episodes/{episode_id}/render")
def render_episode(episode_id: int, payload: RenderRequest,
                   db: Session = Depends(get_db)) -> dict:
    try:
        summary = rendering.render_episode(
            db, episode_id, preset_name=payload.preset)
    except rendering.RenderError as e:
        msg = str(e)
        code = 404 if "episode not found" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from e
    log.info("render_endpoint", render_id=summary["render_id"],
             preset=payload.preset)
    return summary


@router.get("/episodes/{episode_id}/renders")
def list_renders(episode_id: int, db: Session = Depends(get_db)) -> list[dict]:
    if db.get(models.Episode, episode_id) is None:
        raise HTTPException(status_code=404, detail="episode not found")
    rows = (
        db.query(models.Render).filter_by(episode_id=episode_id)
        .order_by(models.Render.id.desc()).all()
    )
    return [_brief(r) for r in rows]


@router.get("/renders/{render_id}")
def get_render(render_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(models.Render, render_id)
    if row is None:
        raise HTTPException(status_code=404, detail="render not found")
    body = _brief(row)
    if row.status == "COMPLETED":
        from pathlib import Path

        from app.domain.rendering.service import load_presets, qa_render

        presets = load_presets()
        preset = presets.get(row.preset, {})
        cap = (Path(row.path).parent.parent / "captions"
               / f"render_{row.id}.ass")
        try:
            ep = db.get(models.Episode, row.episode_id)
            expected = float(ep.actual_duration) if ep else 0.0
            body["qa"] = qa_render(row.path, preset, expected, cap)
        except Exception as e:
            body["qa"] = {"ok": False, "error": str(e)[:300]}
    return body


@router.get("/renders/{render_id}/file")
def get_render_file(render_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Render, render_id)
    if row is None or row.status != "COMPLETED":
        raise HTTPException(status_code=404, detail="render file not found")
    return FileResponse(path=row.path, media_type="video/mp4",
                        filename=f"render_{render_id}.mp4")


@router.post("/renders/{render_id}/cancel")
def cancel_render(render_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(models.Render, render_id)
    if row is None:
        raise HTTPException(status_code=404, detail="render not found")
    if row.status not in ("QUEUED", "RUNNING"):
        raise HTTPException(
            status_code=409,
            detail=f"render {render_id} is {row.status} — retry with a fresh "
                   f"POST /episodes/{row.episode_id}/render",
        )
    row.status = "CANCELLED"
    db.commit()
    return _brief(row)
