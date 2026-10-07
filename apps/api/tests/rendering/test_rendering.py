"""Service-level render tests: 3-clip episode → mp4 + full QA asserts."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.domain.rendering import service as rendering
from tests.rendering.fixtures import seed_episode


@pytest.fixture()
def db(tmp_path):
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    session.roots = [tmp_path]  # type: ignore[attr-defined]
    try:
        yield session
    finally:
        session.close()


def test_render_three_clips_with_qa(db, tmp_path):
    ep_id = seed_episode(db, tmp_path)
    summary = rendering.render_episode(
        db, ep_id, "preview_720p", roots=[tmp_path])
    from pathlib import Path

    out = Path(summary["path"])
    assert out.is_file() and out.stat().st_size > 0
    qa = summary["qa"]
    assert qa["ok"], qa["failed"]
    for check in ("exists", "duration_positive", "duration_matches",
                  "has_video", "has_audio", "resolution", "fps",
                  "captions_present", "clean_decode"):
        assert qa["checks"][check] is True, check
    assert qa["resolution"] == "1280x720"
    # 2s cards + 3x5s clips, captions only over clips
    assert qa["duration"] == 19.0
    row = db.get(models.Render, summary["render_id"])
    assert row.status == "COMPLETED" and row.error == ""
    job = db.query(models.Job).filter_by(type="RENDER").one()
    assert job.status == "COMPLETED"
    ass = tmp_path / "captions" / f"render_{row.id}.ass"
    assert ass.is_file() and ass.stat().st_size > 0
    ass_text = ass.read_text(encoding="utf-8")
    assert "Intro card" in ass_text and "Outro card" in ass_text


def test_render_failure_records_and_raises(db, tmp_path):
    ep = models.Episode(title="Empty", target_duration=60.0)
    db.add(ep)
    db.commit()
    with pytest.raises(rendering.RenderError, match="no segments"):
        rendering.render_episode(db, ep.id, "preview_720p", roots=[tmp_path])
    row = db.query(models.Render).one()
    assert row.status == "FAILED" and "no segments" in row.error


def test_bad_preset(db):
    with pytest.raises(rendering.RenderError, match="unknown preset"):
        rendering.render_episode(db, 1, "nope")


def test_ass_builder_and_events():
    events = rendering.words_to_events(
        [{"start": 0.0, "end": 0.5, "word": " hi", "probability": 1.0},
         {"start": 0.5, "end": 1.0, "word": " there", "probability": 1.0}])
    assert len(events) == 1 and events[0]["text"] == "hi there"
    ass = rendering.build_ass(events, "highlight")
    assert "Dialogue" in ass and "YtPop" in ass and "hi there" in ass


def test_qa_missing_file(tmp_path):
    qa = rendering.qa_render(
        tmp_path / "nope.mp4", rendering.load_presets()["preview_720p"],
        10.0, tmp_path / "nope.ass")
    assert qa["ok"] is False
    assert qa["checks"]["exists"] is False
    assert qa["checks"]["captions_present"] is False


def test_presets_load():
    presets = rendering.load_presets()
    assert set(presets) >= {"preview_720p", "youtube_1080p",
                            "vertical_1080x1920"}
    assert presets["youtube_1080p"]["width"] == 1920
