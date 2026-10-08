"""Learned ranker (S14/V5-preview, D4 training): file-backed weights.

`training.train()` writes the weights file; `apply()` adds the learned
contribution to each candidate's final_score. Without a file (or with
learned_ranking.enabled=false in configs/scoring.yaml) apply() is a logged
passthrough, so the pipeline behaves exactly like V2/V4.
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
    """Adjust final_score in place when weights exist; else passthrough.

    Weights are standardized (features list + coefficients/bias + mean/std
    written by app.domain.clipping.training). Candidates missing a feature
    contribute 0 for it.
    """
    if not weights:
        return scored
    feature_keys = [k for k in (weights.get("features") or [])
                    if isinstance(k, str)]
    coef = weights.get("coefficients") or {}
    mean = weights.get("mean") or {}
    std = weights.get("std") or {}
    bias = float(weights.get("bias", 0.0))

    def zvalue(key: str, raw: float, use_std: bool) -> float:
        sd = float(std.get(key, 1.0) or 1.0)
        if use_std and sd > 1e-9:
            return (raw - float(mean.get(key, 0.0) or 0.0)) / sd
        return raw

    # compressed-vs-standardized detection: a trained payload has mean/std
    trained = bool(mean) and bool(std)
    for cand in scored:
        feats = cand.get("feats", {})
        bump = sum(zvalue(k, float(feats.get(k, 0.0) or 0.0), trained)
                   * float(coef.get(k, 0.0)) for k in feature_keys)
        cand["final_score"] = round(cand["final_score"] + bump, 3)
    log.info("ranker_applied", n=len(scored), trained=trained)
    return scored
