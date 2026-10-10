"""Scene orchestration (D10): detect -> replace rows -> json artifact."""

import json
import structlog
from pathlib import Path
from sqlalchemy.orm import Session

from app.db import models
from app.services import ffmpeg_service as ff
from app.services import scene_service

log = structlog.get_logger()


def load_scene_cfg(cfg: dict | None = None) -> dict:
    if cfg is not None:
        return cfg
    import yaml

    cfg = {}
    from app.db.database import repo_root

    path = repo_root() / "configs" / "default.yaml"
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    return cfg.get("scenes") or {}


def detect_and_store(db: Session, source_id: int, media_path: str | Path,
                     cfg: dict | None = None,
                     roots: list[Path] | None = None) -> dict:
    settings = load_scene_cfg(cfg)
    src = db.get(models.Source, source_id)
    if src is None:
        raise scene_service.SceneError(f"source not found: {source_id}")
    cuts = scene_service.detect_scenes(
        media_path, roots=roots,
        threshold=float(settings.get("threshold", 0.35)),
        max_scenes=int(settings.get("max_scenes", 300)))
    # idempotent: replace this source's rows
    db.query(models.Scene).filter_by(source_id=source_id).delete()
    for i, cut in enumerate(cuts):
        db.add(models.Scene(source_id=source_id, index=i,
                            start_time=cut["start"], score=cut["score"]))
    db.flush()
    artifact = _write_artifact(source_id, cuts, roots)
    log.info("scenes_stored", source_id=source_id, cuts=len(cuts))
    return {"source_id": source_id, "scenes": len(cuts),
            "artifact": str(artifact),
            "cuts": [{"index": i, **c} for i, c in enumerate(cuts)]}


def get_scenes(db: Session, source_id: int) -> list[float]:
    """Cut timestamps only (what the clipping engine needs)."""
    rows = (db.query(models.Scene).filter_by(source_id=source_id)
            .order_by(models.Scene.index.asc()).all())
    return [round(r.start_time, 3) for r in rows]


def list_scenes(db: Session, source_id: int) -> dict:
    rows = (db.query(models.Scene).filter_by(source_id=source_id)
            .order_by(models.Scene.index.asc()).all())
    return {
        "source_id": source_id,
        "scenes": [{"index": r.index, "start_time": r.start_time,
                    "score": r.score} for r in rows],
    }


def _write_artifact(source_id: int, cuts: list[dict],
                    roots: list[Path] | None) -> Path:
    base = (roots or [ff.repo_data_dir()])[0]
    rel = Path("scenes") / f"{source_id}.json"
    out = ff.resolve_data_path(rel, [base])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "source_id": source_id, "cuts": cuts}, indent=2), encoding="utf-8")
    return out
