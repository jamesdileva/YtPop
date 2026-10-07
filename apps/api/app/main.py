import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analysis import router as analysis_router
from app.api.routes.episodes import router as episodes_router
from app.api.routes.health import router as health_router
from app.api.routes.moments import router as moments_router
from app.api.routes.transcription import router as transcription_router
from app.api.routes.sources import router as sources_router
from app.api.routes.trends import router as trends_router
from app.config import settings

log = structlog.get_logger()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.version)
    # Local-first: Electron + Vite dev talk to the API cross-origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(moments_router, prefix="/api/v1")
    app.include_router(analysis_router, prefix="/api/v1")
    app.include_router(episodes_router, prefix="/api/v1")
    app.include_router(transcription_router, prefix="/api/v1")
    app.include_router(sources_router, prefix="/api/v1")
    app.include_router(trends_router, prefix="/api/v1")
    return app


app = create_app()


@app.get("/")
def root() -> dict:
    log.info("root_hit", app=settings.app_name)
    return {"status": "ok", "app": settings.app_name, "version": settings.version}
