"""S4 ingestion tests — real ffmpeg/ffprobe on tiny lavfi fixtures.

Filesystem work stays under tmp_path (guard roots overridden) except the
route test, which uses data/raw/ + cleanup (repo data/ is gitignored).
"""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.main import create_app
from app.services import ffmpeg_service as ff
from app.services import media_ingestion as mi


@pytest.fixture()
def roots(tmp_path: Path) -> list[Path]:
    return [tmp_path]


def gen_av(path: Path, duration: int = 2, audio: bool = True) -> Path:
    cmd = [
        "-y", "-f", "lavfi", "-i",
        "testsrc2=size=128x96:rate=10:duration={}".format(duration),
    ]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration={}".format(duration),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-shortest", str(path)]
    else:
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    ff.run_cmd("ffmpeg", cmd)
    return path


def test_probe_fixture(tmp_path, roots):
    f = gen_av(tmp_path / "fix.mp4")
    info = ff.probe(f, roots)
    assert info["duration"] == pytest.approx(2.0, abs=0.4)
    assert (info["width"], info["height"]) == (128, 96)
    assert info["has_video"] and info["has_audio"]


def test_verify_ok_and_video_only(tmp_path, roots):
    assert mi.verify_media(ff.probe(gen_av(tmp_path / "a.mp4"), roots))["ok"] is True
    verdict = mi.verify_media(ff.probe(gen_av(tmp_path / "v.mp4", audio=False), roots))
    assert verdict["ok"] is False
    assert "no audio stream" in verdict["errors"]


def test_normalize_audio_thumb(tmp_path, roots):
    src = gen_av(tmp_path / "src.mp4")
    norm = ff.normalize(src, tmp_path / "n.mp4", roots=roots)
    audio = ff.extract_audio(src, tmp_path / "a.wav", roots=roots)
    thumb = ff.extract_thumbnail(src, tmp_path / "t.jpg", roots=roots)
    assert norm.stat().st_size > 0 and audio.stat().st_size > 0
    assert thumb.stat().st_size > 0 and thumb.suffix == ".jpg"
    ainfo = ff.probe(audio, roots)
    assert ainfo["has_audio"] and not ainfo["has_video"]


def test_traversal_rejected(tmp_path, roots):
    with pytest.raises(ff.PathTraversalError):
        ff.resolve_data_path("../evil.mp4", roots)
    with pytest.raises(ff.PathTraversalError):
        ff.resolve_data_path("C:/Windows/System32/x.mp4", roots)
    ok = ff.resolve_data_path("sub/ok.mp4", roots)
    assert str(ok).startswith(str(tmp_path.resolve()))


def test_repo_data_dir_is_repo_root():
    """Regression: guard root must be <repo>/data, never <repo>/apps/data."""
    from app.db.database import repo_root

    assert ff.repo_data_dir() == repo_root() / "data"
    assert (repo_root() / "roadmap.md").is_file()


def test_corrupt_fails_safely(tmp_path, roots):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"\x00\x01not a video" * 100)
    with pytest.raises(ff.FFmpegError):
        ff.probe(bad, roots)


def test_shell_metachar_filename(tmp_path, roots):
    """Spaces/metachars must work — proof of arg-array safety (no shell)."""
    tricky = tmp_path / "we;ird $(x) & co.mp4"
    shutil.copy(gen_av(tmp_path / "plain.mp4"), tricky)
    info = ff.probe(tricky, roots)
    assert info["has_video"]


def _mem_client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_ingest_records_assets_and_rights(tmp_path, roots):
    client = _mem_client()
    src_id = client.post("/api/v1/sources", json={
        "external_id": "s4fix", "title": "S4",
    }).json()["id"]
    from app.db.database import get_session_factory  # noqa

    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    row = models.Source(provider="youtube", external_id="s4fix", url="", title="S4")
    db.add(row)
    db.commit()
    fixture = gen_av(roots[0] / "fix.mp4")
    summary = mi.ingest_source(db, row.id, fixture, "user_owned", roots)
    assert summary["duration"] > 0
    kinds = sorted(a.kind for a in db.query(models.MediaAsset).all())
    assert kinds == ["audio", "normalized", "raw", "thumbnail"]
    rights = db.query(models.RightsRecord).one()
    assert rights.status == "USER_OWNED"
    assert db.get(models.Source, row.id).duration > 0
    db.close()


def test_basis_rejected(tmp_path, roots):
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    row = models.Source(provider="youtube", external_id="x", url="")
    db.add(row)
    db.commit()
    with pytest.raises(mi.IngestionError, match="rights basis"):
        mi.ingest_source(db, row.id, "whatever.mp4", "YOUTUBE_RIP", roots)
    db.close()


def test_analyze_route_end_to_end():
    """Route test against repo data/ (gitignored) with fixture cleanup."""
    from app.services.ffmpeg_service import repo_data_dir

    raw = repo_data_dir() / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    fixture = raw / "_test_s4_analyze.mp4"
    gen_av(fixture)
    client = _mem_client()
    src_id = client.post("/api/v1/sources", json={
        "external_id": "s4route", "title": "S4 route",
    }).json()["id"]
    try:
        r = client.post(f"/api/v1/sources/{src_id}/analyze", json={
            "media_path": "raw/_test_s4_analyze.mp4",
            "rights_basis": "USER_OWNED",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["has_video"] and body["asset_id"] > 0

        bad_basis = client.post(f"/api/v1/sources/{src_id}/analyze", json={
            "media_path": "raw/_test_s4_analyze.mp4", "rights_basis": "YOUTUBE_RIP",
        })
        assert bad_basis.status_code == 400

        traversal = client.post(f"/api/v1/sources/{src_id}/analyze", json={
            "media_path": "../../evil.mp4", "rights_basis": "USER_OWNED",
        })
        assert traversal.status_code == 400

        missing = client.post("/api/v1/sources/9999/analyze", json={
            "media_path": "raw/_test_s4_analyze.mp4", "rights_basis": "USER_OWNED",
        })
        assert missing.status_code == 404
    finally:
        fixture.unlink(missing_ok=True)
