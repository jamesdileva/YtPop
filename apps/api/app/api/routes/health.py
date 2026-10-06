from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": settings.version}


@router.get("/health/dependencies")
def health_dependencies() -> dict:
    # S1: static checks only; S2+ wires real DB/YT/Whisper/Ollama/FFmpeg probes.
    return {
        "status": "ok",
        "version": settings.version,
        "dependencies": {
            "api": "ok",
            "database": "not_configured",
            "youtube": "not_configured",
            "whisper": "not_configured",
            "ollama": "not_configured",
            "ffmpeg": "not_configured",
        },
    }
