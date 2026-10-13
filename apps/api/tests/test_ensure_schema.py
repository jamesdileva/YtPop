"""ensure_schema backfills columns on stale packaged DBs, not just tables.

Regression context: a user DB created by an older frozen build had a
discovery_runs table whose created_at column lacked the server default
(NULL on every row, so quota_used_today always read 0 and the quota guard
never tripped). Packaged installs never run Alembic, so ensure_schema must
evolve existing tables too - and ORM inserts must stamp timestamps in
Python (default=_utcnow) so they don't depend on DDL defaults at all.
"""

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db import models  # noqa: F401  (register metadata)
from app.db.base import Base
from app.db.database import ensure_schema, get_engine


def stale_db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'stale.db'}"
    engine = get_engine(url)
    with engine.begin() as conn:
        # discovery_runs as created by the old build: no created_at default
        conn.execute(text(
            "CREATE TABLE discovery_runs (id INTEGER PRIMARY KEY, "
            "run_type VARCHAR(32), region VARCHAR(8), category VARCHAR(64), "
            "units_consumed INTEGER, source_count INTEGER, "
            "created_at DATETIME)"
        ))
        # sources as created by the old build: no created_at column at all
        conn.execute(text(
            "CREATE TABLE sources (id INTEGER PRIMARY KEY, "
            "provider VARCHAR(32), external_id VARCHAR(128))"
        ))
        conn.execute(text(
            "INSERT INTO discovery_runs "
            "(run_type, region, category, units_consumed, source_count) "
            "VALUES ('most_popular', 'US', '', 1, 25)"
        ))
    return url


def test_backfills_missing_columns_and_defaults(tmp_path):
    url = stale_db_url(tmp_path)
    assert ensure_schema(url) is True

    engine = get_engine(url)
    cols = {c["name"]: c for c in inspect(engine).get_columns("sources")}
    assert "discovered_at" in cols
    cols = {c["name"]: c for c in inspect(engine).get_columns("discovery_runs")}
    assert "created_at" in cols

    # pre-existing NULL row keeps working; ORM inserts are stamped in
    # Python even though this table's DDL has no default (the user condition)
    with Session(get_engine(url)) as session:
        session.add(models.DiscoveryRun(
            run_type="search", region="US", category="",
            units_consumed=100, source_count=3,
        ))
        session.commit()
        row = session.query(models.DiscoveryRun).filter_by(
            run_type="search").one()
        assert row.created_at is not None


def test_second_run_is_noop(tmp_path):
    url = stale_db_url(tmp_path)
    assert ensure_schema(url) is True
    assert ensure_schema(url) is False


def test_fresh_db_reports_created(tmp_path):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    assert ensure_schema(url) is True
    tables = set(inspect(get_engine(url)).get_table_names())
    assert set(Base.metadata.tables) <= tables
