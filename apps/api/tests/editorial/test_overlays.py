"""Phase 9 / D11: overlay pack, original graphics, and render burn-in."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.domain.editorial import overlays
from app.domain.editorial import service as editorial
from app.services import ffmpeg_service as ff
from app.services import graphics_service as gfx


def _plan(order, transitions=None, contexts=None, clusters=None):
    body = {
        "title": "Overlay Episode",
        "opening_hook": "Watch this",
        "hook_moment_id": order[0],
        "story_clusters": clusters or [
            {"name": "Main", "moment_ids": order, "rationale": "r"}],
        "segment_order": order,
        "transitions": transitions or [],
        "context_requirements": contexts or [],
        "ending": "That is all", "titles": ["Overlay Episode"],
        "description": "",
    }
    return editorial.EpisodePlan.model_validate(body)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _episode(db, n_clips=2, views=(100_000, 250_000)) -> int:
    ep = models.Episode(title="E", target_duration=1200.0)
    db.add(ep)
    db.flush()
    for i in range(n_clips):
        src = models.Source(
            provider="youtube", external_id=f"ov{i}", url="",
            title=f"Source clip {i}", channel_name=f"Channel {i}",
            view_count=views[i] if i < len(views) else 1000)
        db.add(src)
        db.flush()
        m = models.Moment(source_id=src.id, start_time=0.0, end_time=6.0,
                          transcript_excerpt=f"clip {i}", final_score=80.0,
                          status="APPROVED")
        db.add(m)
        db.flush()
        db.add(models.EpisodeSegment(
            episode_id=ep.id, moment_id=m.id, sequence=i, duration=6.0,
            transition_type="cut",
            commentary_text=f"transition {i}" if i else "",
            context_text=f"context {i}" if i else ""))
    db.commit()
    return ep.id


def test_graphics_are_deterministic(tmp_path):
    rows = [("Channel 1", 250_000), ("Channel 0", 100_000)]
    a = gfx.bar_chart(tmp_path / "a.png", rows, title="Views")
    b = gfx.bar_chart(tmp_path / "b.png", rows, title="Views")
    assert a.read_bytes() == b.read_bytes()
    assert a.stat().st_size > 1000
    strip = gfx.timeline_strip(tmp_path / "t.png",
                              [("intro", 4.0), ("clip 1", 6.0)])
    assert strip.exists() and strip.stat().st_size > 1000


def test_overlay_pack_covers_all_kinds(db, tmp_path):
    ep_id = _episode(db)
    plan = _plan(
        [s.moment_id for s in db.query(models.EpisodeSegment)
         .filter_by(episode_id=ep_id).filter(
             models.EpisodeSegment.moment_id.is_not(None)).all()],
        transitions=[{"after_moment_id": 1, "text": "Next"}],
        contexts=[{"after_moment_id": None, "text": "Previously"}],
        clusters=[{"name": "Two", "moment_ids": [1, 2], "rationale": "r"}])
    out = overlays.build_overlays(db, ep_id, plan, roots=[tmp_path])
    kinds = set(out["kinds"])
    assert {"context", "commentary", "source", "comparison", "chart",
            "timeline", "annotation"} <= kinds
    # narration ships as its own script (text + timing)
    assert out["narration"] and out["narration"][0][1] == "Watch this"
    # graphics exist on disk
    assert any(i["asset_path"] and i["kind"] == "chart"
               for i in out["items"])
    # overlay cards became real segments
    cards = [s for s in db.query(models.EpisodeSegment)
             .filter_by(episode_id=ep_id)
             .filter(models.EpisodeSegment.moment_id.is_(None)).all()]
    assert cards, "overlay cards should be timeline segments"
    assert any(s.context_text.startswith("overlay:") for s in cards)


def test_overlays_are_idempotent(db, tmp_path):
    ep_id = _episode(db)
    plan = _plan([1, 2])
    first = overlays.build_overlays(db, ep_id, plan, roots=[tmp_path])
    cards_a = db.query(models.EpisodeSegment).filter_by(episode_id=ep_id).count()
    second = overlays.build_overlays(db, ep_id, plan, roots=[tmp_path])
    cards_b = db.query(models.EpisodeSegment).filter_by(episode_id=ep_id).count()
    assert cards_a == cards_b, "re-running should not duplicate segments"
    assert {i["id"] for i in first["items"]} == {i["id"] for i in second["items"]}


def test_overlay_requires_clip_segments(db, tmp_path):
    ep = models.Episode(title="empty", target_duration=60.0)
    db.add(ep)
    db.commit()
    with pytest.raises(overlays.OverlayError, match="no clip segments"):
        overlays.build_overlays(db, ep.id, _plan([1]), roots=[tmp_path])


def _gen_clip(path, duration=6, freq=440):
    ff.run_cmd("ffmpeg", [
        "-y", "-f", "lavfi", "-i",
        f"testsrc2=size=320x240:rate=15:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(path)])
    return path


def _episode_with_media(db, tmp_path, n_clips=2) -> int:
    ep_id = _episode(db, n_clips=n_clips)
    segs = (db.query(models.EpisodeSegment)
            .filter_by(episode_id=ep_id)
            .filter(models.EpisodeSegment.moment_id.is_not(None)).all())
    for i, seg in enumerate(segs):
        moment = db.get(models.Moment, seg.moment_id)
        media = _gen_clip(tmp_path / f"ovm{i}.mp4", 6, 440 + i * 60)
        db.add(models.MediaAsset(source_id=moment.source_id, kind="raw",
                                 path=str(media), duration=6.0))
    db.commit()
    return ep_id


def test_render_burns_chart_card_and_annotation(db, tmp_path):
    """A 2-clip episode + overlay cards renders with the chart embedded."""
    from app.domain.rendering import service as rendering

    ep_id = _episode_with_media(db, tmp_path, n_clips=2)
    before = sum(s.duration for s in
                 db.query(models.EpisodeSegment).filter_by(episode_id=ep_id))
    plan = _plan([1, 2],
                 contexts=[{"after_moment_id": None, "text": "Previously"}])
    overlays.build_overlays(db, ep_id, plan, roots=[tmp_path])
    summary = rendering.render_episode(
        db, ep_id, "preview_720p", roots=[tmp_path])
    assert summary["qa"]["ok"], summary["qa"]["failed"]
    after = sum(s.duration for s in
                db.query(models.EpisodeSegment).filter_by(episode_id=ep_id))
    assert after > before + 10, "overlay cards should extend the episode"
    ass = tmp_path / "captions" / f"render_{summary['render_id']}.ass"
    text = ass.read_text(encoding="utf-8")
    assert "Original graphic" in text          # chart card caption
    assert "Overlay Episode" in text           # annotation caption


def test_overlay_route_commits_overlay_cards(db, tmp_path):
    """The overlay cards must survive as segments (route has to commit)."""
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool

    from app.api.routes.overlays import router
    from app.db.database import get_db
    from app.main import create_app

    ep_id = _episode_with_media(db, tmp_path, n_clips=2)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    ep_id = _episode_with_media(db, tmp_path, n_clips=2)

    app = create_app()
    app.include_router(router, prefix="/api/v1")

    def override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    plan = {
        "title": "Route", "opening_hook": "Watch", "hook_moment_id": 1,
        "story_clusters": [{"name": "Main", "moment_ids": [1, 2],
                            "rationale": "r"}],
        "segment_order": [1, 2], "transitions": [],
        "context_requirements": [], "ending": "Bye", "titles": ["Route"],
        "description": "",
    }
    r = client.post(f"/api/v1/episodes/{ep_id}/overlays", json={"plan": plan})
    assert r.status_code == 200, r.text
    segs = (db.query(models.EpisodeSegment)
            .filter_by(episode_id=ep_id).all())
    assert any(s.transition_type == "overlay" for s in segs), \
        "overlay cards were never committed as segments"
    db.close()


def test_render_missing_overlay_asset_fails_loudly(db, tmp_path):
    from app.domain.rendering import service as rendering

    ep_id = _episode_with_media(db, tmp_path, n_clips=1)
    db.add(models.EpisodeSegment(
        episode_id=ep_id, moment_id=None, sequence=99, duration=4.0,
        context_text="overlay:/nope/missing.png"))
    db.commit()
    with pytest.raises(rendering.RenderError, match="overlay asset missing"):
        rendering.render_episode(db, ep_id, "preview_720p", roots=[tmp_path])
