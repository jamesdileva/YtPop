"""Editorial planning tests — scripted fake LLMs, no network."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.domain.editorial import service as editorial


def _plan_dict(order, extra=None):
    order = order or [1]  # placeholder; unused when no candidates exist
    base = {
        "title": "Test Show", "opening_hook": "Watch this",
        "hook_moment_id": order[0],
        "story_clusters": [{"name": "Main", "moment_ids": order,
                            "rationale": "they belong"}],
        "segment_order": order, "transitions": [],
        "context_requirements": [], "ending": "That is all",
        "titles": ["Test Show"], "description": "d",
    }
    base.update(extra or {})
    return base


class ScriptedLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def chat_json(self, system, user):
        self.calls += 1
        reply = self.replies[min(self.calls - 1, len(self.replies) - 1)]
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _moments(db, n=3):
    src = models.Source(provider="youtube", external_id="ed", url="")
    db.add(src)
    db.flush()
    out = []
    for i in range(n):
        m = models.Moment(source_id=src.id, start_time=float(i * 10),
                          end_time=float(i * 10 + 8),
                          transcript_excerpt=f"clip {i}", final_score=80.0,
                          status="APPROVED")
        db.add(m)
        db.flush()
        out.append(m)
    db.commit()
    return out


def test_valid_plan_first_try(db):
    moments = _moments(db)
    order = [m.id for m in moments]
    svc = editorial.EditorialService(ScriptedLLM([_plan_dict(order)]))
    plan, meta = svc.plan(moments=moments)
    assert plan.title == "Test Show"
    assert plan.segment_order == order
    assert meta == {"repairs": 0}


def test_unknown_ids_repaired(db):
    moments = _moments(db)
    order = [m.id for m in moments]
    svc = editorial.EditorialService(ScriptedLLM([
        _plan_dict([999, *order]),
        _plan_dict(order),
    ]))
    plan, meta = svc.plan(moments=moments)
    assert plan.segment_order == order
    assert meta == {"repairs": 1}


def test_garbage_exhausts_repairs(db):
    moments = _moments(db)
    svc = editorial.EditorialService(
        ScriptedLLM([{"nope": True}]), max_repairs=2)
    with pytest.raises(editorial.EditorialError, match="after 2 repairs"):
        svc.plan(moments=moments)


def test_empty_moments_rejected(db):
    with pytest.raises(editorial.EditorialError, match="no candidate"):
        editorial.EditorialService(ScriptedLLM([{}])).plan(moments=[])


def test_schema_rejects_duplicate_order():
    with pytest.raises(ValueError):
        editorial.EpisodePlan.model_validate(
            _plan_dict([1, 1], {"story_clusters": [
                {"name": "x", "moment_ids": [1, 1], "rationale": "r"}]}))


def test_apply_plan_rebuilds_timeline(db, tmp_path):
    moments = _moments(db)
    order = [moments[2].id, moments[0].id]
    ep = models.Episode(title="Old", target_duration=1200.0)
    db.add(ep)
    db.flush()
    db.add(models.EpisodeSegment(
        episode_id=ep.id, moment_id=moments[1].id, sequence=0, duration=8.0,
        transition_type="cut"))
    db.commit()
    plan = editorial.EpisodePlan.model_validate(_plan_dict(
        order,
        {"transitions": [{"after_moment_id": order[0], "text": "Next up"}],
         "context_requirements": [{"after_moment_id": None,
                                   "text": "Previously"}]}))
    result = editorial.apply_plan(db, ep.id, plan, roots=[tmp_path])
    assert result["applied"] == 2 and result["skipped"] == []
    db.commit()
    clips = (db.query(models.EpisodeSegment)
             .filter_by(episode_id=ep.id)
             .filter(models.EpisodeSegment.moment_id.is_not(None))
             .order_by(models.EpisodeSegment.sequence.asc()).all())
    assert [c.moment_id for c in clips] == order
    assert clips[0].commentary_text == "Next up"
    cards = (db.query(models.EpisodeSegment)
             .filter_by(episode_id=ep.id)
             .filter(models.EpisodeSegment.moment_id.is_(None)).all())
    assert any("Previously" in c.context_text for c in cards)
    assert any("That is all" in c.context_text for c in cards)
    assert db.get(models.Episode, ep.id).title == "Test Show"
    import json as _json

    artifact = tmp_path / "storyboards" / f"{ep.id}.json"
    assert artifact.is_file()
    assert _json.loads(artifact.read_text())["title"] == "Test Show"


def test_apply_plan_skips_unapproved(db, tmp_path):
    moments = _moments(db, n=1)
    moments[0].status = "REJECTED"
    db.commit()
    ep = models.Episode(title="E", target_duration=60.0)
    db.add(ep)
    db.commit()
    plan = editorial.EpisodePlan.model_validate(
        _plan_dict([moments[0].id]))
    with pytest.raises(editorial.EditorialError, match="no eligible"):
        editorial.apply_plan(db, ep.id, plan, roots=[tmp_path])
