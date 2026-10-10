import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analysis import router as analysis_router
from app.api.routes.editorial import router as editorial_router
from app.api.routes.episodes import router as episodes_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.moments import router as moments_router
from app.api.routes.renders import router as renders_router
from app.api.routes.rights import router as rights_router
from app.api.routes.scenes import router as scenes_router
from app.api.routes.transcription import router as transcription_router
from app.api.routes.sources import router as sources_router
from app.api.routes.trends import router as trends_router
from app.config import settings

log = structlog.get_logger()


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 24/7 loop is opt-in (YTPOP_SCHEDULER=true) so tests stay quiet.
        if settings.scheduler:
            from app.workers import scheduler as sched

            sched.start_background_loop()
        yield

    app = FastAPI(title=settings.app_name, version=settings.version,
                  lifespan=lifespan)
    # Local-first: Electron + Vite dev talk to the API cross-origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(jobs_router, prefix="/api/v1")
    app.include_router(moments_router, prefix="/api/v1")
    app.include_router(renders_router, prefix="/api/v1")
    app.include_router(scenes_router, prefix="/api/v1")
    app.include_router(rights_router, prefix="/api/v1")
    app.include_router(analysis_router, prefix="/api/v1")
    app.include_router(editorial_router, prefix="/api/v1")
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
