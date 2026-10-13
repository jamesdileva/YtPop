"""Engine/session helpers. DB path resolves to repo root when relative."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import structlog

from app.config import settings

log = structlog.get_logger()


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


def ensure_schema(url: str | None = None) -> bool:
    """Create missing tables AND missing columns from model metadata.

    Dev/test flows use Alembic; the packaged (frozen) backend uses this so a
    first run on a fresh data dir works without shipping migrations.

    Column backfill matters because ensure_schema historically only added
    whole tables: a DB created by an older build keeps stale tables (e.g. a
    discovery_runs without the created_at default, or a sources table
    without created_at at all), which silently breaks quota accounting.
    Returns True if it had to create or alter anything.
    """
    from app.db import models  # noqa: F401  (register metadata)
    from app.db.base import Base
    from sqlalchemy import inspect, text

    engine = get_engine(url)
    changed = False
    existing = set(inspect(engine).get_table_names())
    missing_tables = set(Base.metadata.tables) - existing
    if missing_tables:
        resolve_db_path().parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(engine)
        changed = True
        existing |= missing_tables
    with engine.begin() as conn:
        for table in Base.metadata.tables.values():
            if table.name not in existing:
                continue
            present = {
                c["name"] for c in inspect(conn).get_columns(table.name)
            }
            for column in table.columns:
                if column.name in present:
                    continue
                if not column.nullable and column.server_default is None:
                    log.warning(
                        "ensure_schema_skip",
                        table=table.name, column=column.name,
                        reason="not-null without default",
                    )
                    continue
                ddl = (
                    f"ALTER TABLE {table.name} ADD COLUMN {column.name} "
                    f"{column.type.compile(dialect=engine.dialect)}"
                )
                if column.server_default is not None:
                    default = column.server_default.arg.compile(
                        engine, compile_kwargs={"literal_binds": True}
                    )
                    ddl += f" DEFAULT {default}"
                conn.execute(text(ddl))
                changed = True
    return changed


def init_db(url: str | None = None) -> Engine:
    """Create parent dirs + tables (dev fallback; Alembic is source of truth)."""
    from app.db import models  # noqa: F401  (register metadata)
    from app.db.base import Base

    resolve_db_path().parent.mkdir(parents=True, exist_ok=True)
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    return engine
