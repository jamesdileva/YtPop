"""Rights gate (S12): state machine + publish blocker.

Every source starts UNKNOWN. Nothing is publishable without an approved
basis recorded by a human reviewer — the app never claims "fair use
confirmed" or any equivalent. Demo mode (default on) blocks publishing
unconditionally: analyze locally all you want, nothing is cleared.
"""

import structlog
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db import models

log = structlog.get_logger()


class RightsError(RuntimeError):
    pass


# S4 ingestion bases behave as approved leaves (human-supplied basis).
_APPROVED_LEAVES = frozenset({
    "USER_OWNED", "LICENSED", "CREATIVE_COMMONS", "PUBLIC_DOMAIN",
})

TRANSITIONS: dict[str, frozenset[str]] = {
    "UNKNOWN": frozenset({"REVIEW_REQUIRED", "REJECTED"}),
    "REVIEW_REQUIRED": frozenset({"APPROVED", "REJECTED", "NEEDS_PERMISSION"}),
    "NEEDS_PERMISSION": frozenset({"PERMISSION_GRANTED", "REJECTED"}),
    "PERMISSION_GRANTED": frozenset({"REVIEW_REQUIRED", "REJECTED"}),
    "APPROVED": frozenset({"REVIEW_REQUIRED", "REJECTED"}),
    "REJECTED": frozenset({"REVIEW_REQUIRED"}),
}
for _leaf in _APPROVED_LEAVES:
    TRANSITIONS[_leaf] = frozenset({"REVIEW_REQUIRED", "REJECTED"})

APPROVED_SET = frozenset(
    {"APPROVED", "PERMISSION_GRANTED"} | _APPROVED_LEAVES)


def is_expired(row: models.RightsRecord) -> bool:
    if row.expires_at is None:
        return False
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp <= datetime.now(timezone.utc)


def _payload(row: models.RightsRecord) -> dict:
    return {
        "id": row.id, "source_id": row.source_id, "status": row.status,
        "basis": row.basis, "owner": row.owner, "license": row.license,
        "permission_reference": row.permission_reference,
        "restrictions": row.restrictions, "territory": row.territory,
        "commercial_allowed": row.commercial_allowed, "notes": row.notes,
        "reviewer": row.reviewer,
        "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


def default_payload(source_id: int) -> dict:
    return {
        "id": None, "source_id": source_id, "status": "UNKNOWN",
        "basis": "", "owner": "", "license": "", "permission_reference": "",
        "restrictions": "", "territory": "", "commercial_allowed": False,
        "notes": "", "reviewer": "", "verified_at": None, "expires_at": None,
    }


def _require_source(db: Session, source_id: int) -> models.Source:
    row = db.get(models.Source, source_id)
    if row is None:
        raise RightsError(f"source not found: {source_id}")
    return row


def get_rights(db: Session, source_id: int) -> dict:
    _require_source(db, source_id)
    row = db.query(models.RightsRecord).filter_by(
        source_id=source_id).one_or_none()
    return _payload(row) if row else default_payload(source_id)


def _ensure_row(db: Session, source_id: int) -> models.RightsRecord:
    _require_source(db, source_id)
    row = db.query(models.RightsRecord).filter_by(
        source_id=source_id).one_or_none()
    if row is None:
        row = models.RightsRecord(source_id=source_id, status="UNKNOWN")
        db.add(row)
        db.flush()
    return row


def _transition(row: models.RightsRecord, target: str,
                reviewer: str | None) -> None:
    allowed = TRANSITIONS.get(row.status, frozenset())
    if target not in allowed:
        raise RightsError(
            f"illegal rights transition {row.status} → {target}; "
            f"allowed: {sorted(allowed) or 'none'}")
    if target in APPROVED_SET and not (reviewer or row.reviewer):
        raise RightsError(
            f"reviewer required to approve (→ {target}) — "
            "a human must take responsibility")
    row.status = target
    if reviewer:
        row.reviewer = reviewer
    row.verified_at = datetime.now(timezone.utc)
    log.info("rights_transition", source_id=row.source_id,
             status=target, reviewer=row.reviewer)


def request_review(db: Session, source_id: int, note: str = "") -> dict:
    row = _ensure_row(db, source_id)
    if row.status != "REVIEW_REQUIRED":
        _transition(row, "REVIEW_REQUIRED", reviewer=None)
    if note:
        row.notes = ((row.notes + "\n" if row.notes else "") + note)[:2000]
    db.flush()
    return _payload(row)


_ALLOWED_FIELDS = {"basis", "owner", "license", "permission_reference",
                   "restrictions", "territory", "commercial_allowed",
                   "notes", "reviewer", "expires_at"}


def update_rights(db: Session, source_id: int, fields: dict) -> dict:
    row = _ensure_row(db, source_id)
    unknown = set(fields) - _ALLOWED_FIELDS - {"status"}
    if unknown:
        raise RightsError(f"unknown rights fields: {sorted(unknown)}")
    if "status" in fields and fields["status"] is not None:
        _transition(row, fields["status"],
                    fields.get("reviewer") or None)
    for key in _ALLOWED_FIELDS:
        if key in fields and fields[key] is not None:
            setattr(row, key, fields[key])
    db.flush()
    return _payload(row)


def publish_verdict(db: Session, source_id: int,
                    demo_mode: bool) -> dict:
    """The publish blocker: publishable only with an approved, live basis."""
    _require_source(db, source_id)
    row = db.query(models.RightsRecord).filter_by(
        source_id=source_id).one_or_none()
    reasons: list[str] = []
    if demo_mode:
        reasons.append("demo mode: publishing disabled "
                       "(set YTPOP_DEMO_MODE=false after human review)")
    if row is None:
        reasons.append("no rights record — status UNKNOWN")
    else:
        if row.status not in APPROVED_SET:
            reasons.append(f"status {row.status} is not an approved basis "
                           f"(approved: {sorted(APPROVED_SET)})")
        if is_expired(row):
            reasons.append("rights basis expired — re-review required")
    return {
        "source_id": source_id,
        "status": row.status if row else "UNKNOWN",
        "publishable": not reasons,
        "reasons": reasons,
    }


def episode_verdict(db: Session, episode_id: int,
                    demo_mode: bool) -> dict:
    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise RightsError(f"episode not found: {episode_id}")
    segs = (db.query(models.EpisodeSegment)
            .filter_by(episode_id=episode_id)
            .filter(models.EpisodeSegment.moment_id.is_not(None)).all())
    source_ids = sorted({
        db.get(models.Moment, s.moment_id).source_id
        for s in segs if db.get(models.Moment, s.moment_id) is not None
    })
    checks = [publish_verdict(db, sid, demo_mode) for sid in source_ids]
    publishable = bool(source_ids) and all(c["publishable"] for c in checks)
    return {
        "episode_id": episode_id,
        "publishable": publishable,
        "ready_to_publish": publishable,
        "sources": checks,
        "blocked": [c for c in checks if not c["publishable"]],
    }
