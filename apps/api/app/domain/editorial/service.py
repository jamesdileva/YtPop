"""Editorial engine (S10): approved moments → story plan → timeline.

The model answers "why do these clips belong together?" — grouping,
ordering, transitions and context — never just top-score sorting.
Raw model output is validated with Pydantic; max 2 repair retries, then
a clear EditorialError. Only APPROVED moments are eligible (rights gate).
"""

import json
import structlog
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db import models
from app.services import ffmpeg_service as ff

log = structlog.get_logger()


class EditorialError(RuntimeError):
    pass


class StoryCluster(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    moment_ids: list[int] = Field(min_length=1)
    rationale: str = Field(default="", max_length=500)


class Transition(BaseModel):
    after_moment_id: int
    text: str = Field(min_length=1, max_length=500)


class ContextRequirement(BaseModel):
    after_moment_id: int | None = None
    text: str = Field(min_length=1, max_length=500)


class EpisodePlan(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    opening_hook: str = Field(min_length=1, max_length=500)
    hook_moment_id: int | None = None
    story_clusters: list[StoryCluster] = Field(min_length=1)
    segment_order: list[int] = Field(min_length=1)
    transitions: list[Transition] = Field(default_factory=list)
    context_requirements: list[ContextRequirement] = Field(default_factory=list)
    ending: str = Field(min_length=1, max_length=500)
    titles: list[str] = Field(min_length=1)
    description: str = Field(default="", max_length=2000)

    @field_validator("segment_order")
    @classmethod
    def _unique_order(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("segment_order must not repeat moment ids")
        return v


SYSTEM_PROMPT = """You are the story editor of a highlights show. Given candidate moments \
(each with id, score, type and transcript excerpt), group them into story clusters, \
order them into a compelling timeline (hook first, then context, escalation, payoff), \
and write the transitions, context cards and ending.

Rules:
- Use ONLY the moment ids from the input. Never invent ids.
- segment_order must contain each chosen moment id exactly once.
- Every transition/context must reference a moment id from segment_order (or null for the intro card).
- Reply with a single JSON object matching this schema (no markdown, no commentary):
{"title": str, "opening_hook": str, "hook_moment_id": int|null,
 "story_clusters": [{"name": str, "moment_ids": [int], "rationale": str}],
 "segment_order": [int],
 "transitions": [{"after_moment_id": int, "text": str}],
 "context_requirements": [{"after_moment_id": int|null, "text": str}],
 "ending": str, "titles": [str], "description": str}"""


def _summarize_moments(moments: list[models.Moment]) -> list[dict]:
    return [{
        "id": m.id, "source_id": m.source_id, "type": m.moment_type,
        "score": m.final_score, "start": m.start_time, "end": m.end_time,
        "excerpt": (m.transcript_excerpt or "")[:300],
    } for m in moments]


class EditorialService:
    def __init__(self, llm, max_repairs: int = 2) -> None:
        self.llm = llm
        self.max_repairs = max_repairs

    def plan(self, *, trend: str = "", sources: list[dict] | None = None,
             moments: list[models.Moment] | None = None,
             target_duration: float = 1200.0,
             format: str = "daily_highlights") -> tuple[EpisodePlan, dict]:
        moments = moments or []
        if not moments:
            raise EditorialError("no candidate moments to plan from")
        eligible = {m.id for m in moments}
        user = json.dumps({
            "trend": trend, "format": format,
            "target_duration_seconds": target_duration,
            "sources": sources or [],
            "candidate_moments": _summarize_moments(moments),
        })
        errors: list[str] = []
        for attempt in range(self.max_repairs + 1):
            prompt = user if attempt == 0 else (
                user + "\n\nYour previous reply was invalid:\n"
                + "\n".join(errors)
                + "\nReply with corrected JSON only.")
            try:
                raw = self.llm.chat_json(SYSTEM_PROMPT, prompt)
            except Exception as e:
                raise EditorialError(f"editorial model call failed: {e}") from e
            try:
                plan = EpisodePlan.model_validate(raw)
            except Exception as e:
                errors = [f"- {err['loc']}: {err['msg']}"
                          for err in getattr(e, "errors", lambda: [])()]
                log.info("plan_repair", attempt=attempt, errors=errors)
                continue
            unknown = (
                {i for c in plan.story_clusters for i in c.moment_ids}
                | set(plan.segment_order)
                | {t.after_moment_id for t in plan.transitions}
                | {c.after_moment_id for c in plan.context_requirements
                   if c.after_moment_id is not None}
                | ({plan.hook_moment_id} if plan.hook_moment_id else set())
            ) - eligible
            if unknown:
                errors = [f"- unknown moment ids (not in candidates): "
                          f"{sorted(unknown)}"]
                log.info("plan_repair", attempt=attempt, errors=errors)
                continue
            log.info("plan_ok", title=plan.title, repairs=attempt,
                     segments=len(plan.segment_order))
            return plan, {"repairs": attempt}
        raise EditorialError(
            "editorial plan failed validation after "
            f"{self.max_repairs} repairs: {errors}")


def apply_plan(db: Session, episode_id: int, plan: EpisodePlan,
               roots: list[Path] | None = None) -> dict:
    """Replace clip segments with the planned order (+ context/transitions).

    Keeps existing title cards, appends the ending card, stores the full
    plan as a storyboard artifact linked via a media_asset row.
    """
    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise EditorialError(f"episode not found: {episode_id}")
    by_id = {}
    skipped: list[dict] = []
    for mid in plan.segment_order:
        m = db.get(models.Moment, mid)
        if m is None or m.status != "APPROVED":
            skipped.append({"moment_id": mid,
                            "reason": "missing" if m is None else m.status})
            continue
        by_id[mid] = m
    if not by_id:
        raise EditorialError("no eligible APPROVED moments in plan")

    cards = (db.query(models.EpisodeSegment)
             .filter_by(episode_id=episode_id).filter(
                 models.EpisodeSegment.moment_id.is_(None)).all())
    db.query(models.EpisodeSegment).filter_by(
        episode_id=episode_id).filter(
            models.EpisodeSegment.moment_id.is_not(None)).delete()
    order = [mid for mid in plan.segment_order if mid in by_id]
    transitions = {t.after_moment_id: t.text for t in plan.transitions}
    contexts: dict[int | None, list[str]] = {}
    for c in plan.context_requirements:
        contexts.setdefault(c.after_moment_id, []).append(c.text)
    seq = max([s.sequence for s in cards], default=-1) + 1
    if None in contexts:
        for text in contexts[None]:
            db.add(models.EpisodeSegment(
                episode_id=episode_id, moment_id=None, sequence=seq,
                duration=4.0, transition_type="cut", context_text=text))
            seq += 1
    for mid in order:
        m = by_id[mid]
        seg = models.EpisodeSegment(
            episode_id=episode_id, moment_id=mid, sequence=seq,
            duration=round(m.end_time - m.start_time, 3),
            transition_type="cut",
            commentary_text=transitions.get(mid, ""),
            context_text="\n".join(contexts.get(mid, "")),
        )
        db.add(seg)
        db.flush()
        seq += 1
    db.add(models.EpisodeSegment(
        episode_id=episode_id, moment_id=None, sequence=seq,
        duration=5.0, transition_type="fade", context_text=plan.ending))
    ep.title = plan.title
    db.flush()

    base = (roots or [ff.repo_data_dir()])[0]
    rel = Path("storyboards") / f"{episode_id}.json"
    out = ff.resolve_data_path(rel, [base])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    db.add(models.MediaAsset(
        source_id=by_id[order[0]].source_id, kind="storyboard",
        path=str(out))
    )
    db.flush()
    # resequence cards-first? keep insertion order stable by sequence
    log.info("plan_applied", episode_id=episode_id, clips=len(order),
             skipped=len(skipped))
    return {"applied": len(order), "skipped": skipped,
            "artifact": str(out)}
