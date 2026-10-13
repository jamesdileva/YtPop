"""config.py .env precedence: real env > user-data .env > repo .env.

Regression test for the packaged Discover 500: a copied repo .env carrying
the dev-relative YTPOP_DB_PATH used to stomp the shell's absolute DB path
(the data file loaded with override=True) and broke every DB endpoint.
"""

import os

import pytest

from app.config import _load_file_env


@pytest.fixture
def clean_env(monkeypatch):
    for var in ("YTPOP_DB_PATH", "YTPOP_YOUTUBE_API_KEY", "YTPOP_ONLY_REPO"):
        monkeypatch.delenv(var, raising=False)


def test_real_env_wins_over_both_files(tmp_path, monkeypatch, clean_env):
    data = tmp_path / "data.env"
    data.write_text("YTPOP_DB_PATH=file-data\nYTPOP_YOUTUBE_API_KEY=file-data\n")
    repo = tmp_path / "repo.env"
    repo.write_text("YTPOP_DB_PATH=file-repo\nYTPOP_YOUTUBE_API_KEY=file-repo\n")
    monkeypatch.setenv("YTPOP_DB_PATH", "/real/db.sqlite")
    _load_file_env(data, repo)
    assert os.environ["YTPOP_DB_PATH"] == "/real/db.sqlite"
    assert os.environ["YTPOP_YOUTUBE_API_KEY"] == "file-data"


def test_data_env_wins_over_repo(tmp_path, clean_env):
    data = tmp_path / "data.env"
    data.write_text("YTPOP_YOUTUBE_API_KEY=from-data\n")
    repo = tmp_path / "repo.env"
    repo.write_text(
        "YTPOP_YOUTUBE_API_KEY=from-repo\nYTPOP_ONLY_REPO=yes\n"
    )
    _load_file_env(data, repo)
    assert os.environ["YTPOP_YOUTUBE_API_KEY"] == "from-data"
    assert os.environ["YTPOP_ONLY_REPO"] == "yes"


def test_repo_fills_gaps_and_missing_files_ok(tmp_path, clean_env):
    repo = tmp_path / "repo.env"
    repo.write_text("YTPOP_ONLY_REPO=yes\n")
    _load_file_env(tmp_path / "nope.env", repo)
    assert os.environ["YTPOP_ONLY_REPO"] == "yes"
    _load_file_env(tmp_path / "nope.env", tmp_path / "also-nope.env")
