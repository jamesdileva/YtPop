"""Engine/session helpers. DB path resolves to repo root when relative."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def repo_root() -> Path:
    """Repo (or packaged) root used for configs/ and data/.

    `YTPOP_ROOT` overrides the path so the packaged Electron shell can point
    the backend at the bundled files (resources/) instead of the source
    checkout - parents[4] is meaningless inside an asar.
    """
    import os

    override = os.environ.get("YTPOP_ROOT")
    if override:
        return Path(override).resolve()
    # app/db/database.py -> parents[4] == repo root (YtPop/)
    return Path(__file__).resolve().parents[4]


def resolve_db_path(raw: str = settings.db_path) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return repo_root() / p


def database_url(raw: str = settings.db_path) -> str:
    return f"sqlite:///{resolve_db_path(raw)}"


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine(url: str | None = None) -> Engine:
    global _engine
    if _engine is None or url is not None:
        _engine = create_engine(url or database_url(), future=True)
    return _engine


def get_session_factory(url: str | None = None) -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None or url is not None:
        _SessionLocal = sessionmaker(
            bind=get_engine(url), autoflush=False, expire_on_commit=False
        )
    return _SessionLocal


def get_db() -> Iterator[Session]:
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def init_db(url: str | None = None) -> Engine:
    """Create parent dirs + tables (dev fallback; Alembic is source of truth)."""
    from app.db import models  # noqa: F401  (register metadata)
    from app.db.base import Base

    resolve_db_path().parent.mkdir(parents=True, exist_ok=True)
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    return engine
