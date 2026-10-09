"""YTPOP_ROOT resolution for configs/data in dev vs packaged runs."""

from pathlib import Path

import pytest

from app.db import database


def test_repo_root_default_is_source_tree():
    expected = Path(database.__file__).resolve().parents[4]
    assert database.repo_root() == expected
    assert (expected / "roadmap.md").is_file()


def test_repo_root_honours_env(monkeypatch, tmp_path):
    sentinel = tmp_path / "packaged-root"
    sentinel.mkdir()
    monkeypatch.setenv("YTPOP_ROOT", str(sentinel))
    assert database.repo_root() == sentinel.resolve()


def test_resolve_db_path_follows_override(monkeypatch, tmp_path):
    monkeypatch.setenv("YTPOP_ROOT", str(tmp_path))
    resolved = database.resolve_db_path("data/database/mega_clipper.db")
    assert resolved == tmp_path / "data" / "database" / "mega_clipper.db"
    url = database.database_url()
    assert str(resolved) in url or url.endswith("mega_clipper.db")
