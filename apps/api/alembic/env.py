"""Alembic environment — SQLite, single-head, autogenerate from Base.metadata."""

from alembic import context
from sqlalchemy import create_engine

from app.config import settings
from app.db import models  # noqa: F401  (register all tables)
from app.db.base import Base
from app.db.database import database_url, resolve_db_path

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    resolve_db_path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url(), future=True)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
