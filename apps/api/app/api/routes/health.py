from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": settings.version}


@router.get("/health/dependencies")
def health_dependencies() -> dict:
    deps: dict[str, str] = {
        "api": "ok",
        "youtube": "not_configured",
        "whisper": "not_configured",
        "ollama": "not_configured",
    }
    try:
        import shutil

        if shutil.which("ffmpeg") and shutil.which("ffprobe"):
            deps["ffmpeg"] = "ok"
        else:
            deps["ffmpeg"] = "unavailable"
    except Exception:
        deps["ffmpeg"] = "unavailable"
    try:
        from sqlalchemy import text

        from app.db.database import get_engine

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        deps["database"] = "ok"
    except Exception:
        deps["database"] = "unavailable"
    return {
        "status": "ok",
        "version": settings.version,
        "dependencies": deps,
    }
