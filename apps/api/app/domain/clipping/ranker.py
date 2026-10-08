"""Learned ranker stub (S14/V5-preview): file-backed weights, identity fallback.

The feedback export (GET /feedback/export) is the training dataset.
Until a weights file exists, apply() is a logged passthrough so the
pipeline behaves exactly like V2/V4.
"""

import structlog
from pathlib import Path

log = structlog.get_logger()


def load_weights(path: str | Path | None) -> dict | None:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.is_file():
        return None
    import json as _json

    try:
        return _json.loads(candidate.read_text(encoding="utf-8"))
    except ValueError:
        return None


def apply(scored: list[dict], weights: dict | None) -> list[dict]:
    """Adjust final_score in place when weights exist; else passthrough."""
    if not weights:
        return scored
    feature_keys = [k for k in (weights.get("features") or [])
                    if isinstance(k, str)]
    coef = weights.get("coefficients") or {}
    for cand in scored:
        feats = cand.get("feats", {})
        bump = sum(float(feats.get(k, 0.0)) * float(coef.get(k, 0.0))
                   for k in feature_keys)
        cand["final_score"] = round(cand["final_score"] + bump, 3)
    log.info("ranker_applied", n=len(scored))
    return scored
