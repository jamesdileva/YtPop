import structlog
from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.sources import router as sources_router
from app.config import settings

log = structlog.get_logger()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.version)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(sources_router, prefix="/api/v1")
    return app


app = create_app()


@app.get("/")
def root() -> dict:
    log.info("root_hit", app=settings.app_name)
    return {"status": "ok", "app": settings.app_name, "version": settings.version}
