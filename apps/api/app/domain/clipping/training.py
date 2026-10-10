"""Feedback -> learned weights (D4, V5).

Trains logistic regression over the features persisted with each candidate
moment (moments.features_json), labelled by human review decisions in
moment_feedback. Runs as a local ops script:

    python -m app.domain.clipping.training --out data/models/ranker.json

Design notes:
- Pure Python (no numpy/sklearn): keeps the packaged app dependency-free
  and the maths auditable. Batch gradient descent, standardized features,
  L2 penalty, deterministic (no shuffling, fixed learning rate/iters).
- Only clear labels train: APPROVED (and S4 approved bases) are 1, REJECTED
  is 0. TRIMMED/NOTED are ambiguous about the window itself and are skipped.
- Refuses to train on too-few rows or single-class data rather than writing
  a useless weights file.

The file is consumed by app.domain.clipping.ranker.apply at
find_moments time when configs/scoring.yaml sets learned_ranking.enabled.
"""

import json
import math
import structlog
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import models

log = structlog.get_logger()

APPROVED_DECISIONS = frozenset({
    "APPROVED", "PERMISSION_GRANTED", "USER_OWNED", "LICENSED",
    "CREATIVE_COMMONS", "PUBLIC_DOMAIN",
})
REJECTED_DECISIONS = frozenset({"REJECTED"})
AMBIGUOUS_DECISIONS = frozenset({"TRIMMED", "NOTED"})


class TrainingError(RuntimeError):
    pass


def _feature_names(feature_maps: list[dict]) -> list[str]:
    """Stable, sorted union of features actually present in the data."""
    names = {k for feats in feature_maps for k in feats}
    return sorted(names)




def _stats(columns: dict[int, list[float]]) -> tuple[list[float], list[float]]:
    means = [sum(col) / len(col) for col in columns.values()]
    variances = [
        sum((v - m) ** 2 for v in col) / len(col)
        for col, m in zip(columns.values(), means)
    ]
    stds = [math.sqrt(var) for var in variances]
    return means, stds


def train_logistic(rows: list[list[float]], labels: list[int],
                   lr: float = 0.5, l2: float = 0.01,
                   iters: int = 400) -> tuple[list[float], float, list[float],
                                              list[float]]:
    """Deterministic batch-GD logistic regression on standardized features.

    Returns (coefficients, bias, mean, std).
    """
    n = len(rows)
    if n == 0:
        raise TrainingError("no training rows")
    width = len(rows[0])
    for r in rows:
        if len(r) != width:
            raise TrainingError("ragged feature matrix")
    n_features = width
    columns = {
        j: [rows[i][j] for i in range(n)] for j in range(n_features)
    }
    means, stds = _stats(columns)
    std_rows = [
        [(row[j] - means[j]) / (stds[j] if stds[j] > 1e-9 else 1.0)
         for j in range(n_features)]
        for row in rows
    ]
    coef = [0.0] * n_features
    bias = 0.0
    for _ in range(iters):
        grad = [0.0] * n_features
        grad_b = 0.0
        for features, label in zip(std_rows, labels):
            z = bias + sum(c * f for c, f in zip(coef, features))
            p = 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))
            err = p - label
            for j in range(n_features):
                grad[j] += err * features[j] + l2 * coef[j] / n
            grad_b += err
        for j in range(n_features):
            coef[j] -= lr * grad[j] / n
        bias -= lr * grad_b / n
    return coef, bias, means, stds


def build_dataset(db: Session) -> tuple[list[dict], list[int], list[str]]:
    """Labelled feature maps from review decisions; skips ambiguous labels."""
    rows, labels = [], []
    decision_counts: dict[str, int] = {}
    source_map = {fp.id: fp for fp in db.query(models.MomentFeedback).all()}
    for fb in source_map.values():
        decision_counts[fb.decision] = decision_counts.get(fb.decision, 0) + 1
        if fb.decision in APPROVED_DECISIONS:
            label = 1
        elif fb.decision in REJECTED_DECISIONS:
            label = 0
        else:
            continue
        moment = db.get(models.Moment, fb.moment_id)
        if moment is None or not moment.features_json:
            continue
        try:
            feats = json.loads(moment.features_json)
        except ValueError:
            continue
        if not isinstance(feats, dict):
            continue
        rows.append(feats)
        labels.append(label)
    decisions = sorted(decision_counts)
    return rows, labels, decisions


def split_indices(
    n: int, test_every: int = 4, labels: list[int] | None = None
) -> tuple[list[int], list[int]]:
    """Deterministic holdout split keeping BOTH classes in both splits.

    A naive every-Nth split fails on perfectly separable data (e.g.
    [1,0,1,0,...] puts all negatives in train and all positives in test),
    which makes AUC 0.5 regardless of model quality. With labels given, the
    split is class-balanced: it walks the rows, dumping each into test until
    it holds `max(1, count // test_every)` of each class, then fills train.
    Without labels it degrades to the alternating every-Nth split.
    """
    if n <= 2:
        return list(range(n)), []
    test: list[int] = []
    train: list[int] = []
    if labels is None:
        for i in range(n):
            (test if len(test) + len(train) % 1 == 0 and
             (len(test) + len(train)) % test_every == 0 else train).append(i)
        if not test:
            test.append(train.pop())
        return train, test
    quota = max(1, sum(1 for y in labels if y == 1) // test_every)
    pos_in_test = neg_in_test = 0
    for i in range(n):
        label = labels[i]
        if (pos_in_test < quota if label == 1 else neg_in_test < quota) and \
                (len(train) >= 2):
            test.append(i)
            if label == 1:
                pos_in_test += 1
            else:
                neg_in_test += 1
        else:
            train.append(i)
    if not test:
        test.append(train.pop())
    return train, test


def predict(weights: dict, features: list[dict]) -> list[float]:
    """P(label=1) for each feature dict using stored standardization."""
    names = [k for k in (weights.get("features") or []) if isinstance(k, str)]
    coef = weights.get("coefficients") or {}
    mean = weights.get("mean") or {}
    std = weights.get("std") or {}
    bias = float(weights.get("bias", 0.0))
    probs = []
    for feats in features:
        z = bias
        for name in names:
            sd = float(std.get(name, 1.0) or 1.0)
            raw = float(feats.get(name, 0.0) or 0.0)
            z += (raw - float(mean.get(name, 0.0) or 0.0)) / (sd or 1.0) * \
                float(coef.get(name, 0.0))
        probs.append(1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0))))
    return probs


def _auc(probs: list[float], labels: list[int]) -> float:
    pos = [p for p, y in zip(probs, labels) if y == 1]
    neg = [p for p, y in zip(probs, labels) if y == 0]
    if not pos or not neg:
        return 0.5
    wins = ties = 0
    for p in pos:
        for n in neg:
            wins += 1 if p > n else 0
            ties += 1 if p == n else 0
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def evaluate(weights: dict, features: list[dict], labels: list[int]) -> dict:
    """Holdout accuracy + AUC (0.5 = coin flip)."""
    if not features:
        return {"n": 0, "accuracy": 0.0, "auc": 0.5, "error": "empty holdout"}
    probs = predict(weights, features)
    correct = sum(1 for p, y in zip(probs, labels) if (p >= 0.5) == bool(y))
    return {
        "n": len(labels),
        "accuracy": round(correct / len(labels), 4),
        "auc": round(_auc(probs, labels), 4),
    }


def train(db: Session, min_rows: int = 10) -> dict:
    """Build the dataset and fit; returns the weights payload."""
    feats, labels, decisions = build_dataset(db)
    if len(feats) < min_rows:
        raise TrainingError(
            f"need at least {min_rows} labelled rows, got {len(feats)}")
    if len(set(labels)) < 2:
        raise TrainingError(
            "need both approved and rejected rows to train")
    names = _feature_names(feats)
    if not names:
        raise TrainingError("no features present in labelled rows")
    matrix = [[float(f.get(name, 0.0) or 0.0) for name in names]
              for f in feats]
    coef, bias, means, stds = train_logistic(matrix, labels)
    log.info("ranker_trained", rows=len(matrix), features=len(names))
    return {
        "version": 1,
        "features": names,
        "coefficients": {n: round(c, 6) for n, c in zip(names, coef)},
        "bias": round(bias, 6),
        "mean": {n: round(m, 6) for n, m in zip(names, means)},
        "std": {n: round(s, 6) for n, s in zip(names, stds)},
        "meta": {
            "rows": len(matrix),
            "positive": int(sum(labels)),
            "negative": int(len(labels) - sum(labels)),
            "decisions_seen": decisions,
        },
    }


def train_from(rows: list[dict], labels: list[int],
               decisions: list[str] | None = None) -> dict:
    """Fit on an explicit subset (used by the holdout retraining path)."""
    if not rows:
        raise TrainingError("no rows to train on")
    if len(set(labels)) < 2:
        raise TrainingError(
            "need both approved and rejected rows to train on this split")
    names = _feature_names(rows)
    if not names:
        raise TrainingError("no features present in labelled rows")
    matrix = [[float(f.get(name, 0.0) or 0.0) for name in names]
              for f in rows]
    coef, bias, means, stds = train_logistic(matrix, labels)
    return {
        "version": 1,
        "features": names,
        "coefficients": {n: round(c, 6) for n, c in zip(names, coef)},
        "bias": round(bias, 6),
        "mean": {n: round(m, 6) for n, m in zip(names, means)},
        "std": {n: round(s, 6) for n, s in zip(names, stds)},
        "meta": {
            "rows": len(matrix),
            "positive": int(sum(labels)),
            "negative": int(len(labels) - sum(labels)),
            "decisions_seen": decisions or [],
        },
    }


def write_weights(weights: dict, out_path: str | Path) -> Path:
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(weights, indent=2), encoding="utf-8")
    meta = weights.get("meta") or {}
    log.info("weights_written", path=str(target), rows=meta.get("rows"))
    return target


def _cli(argv: list[str] | None = None) -> int:
    import argparse

    from app.db.database import get_session_factory

    parser = argparse.ArgumentParser(
        description="Train the clip ranker from review feedback")
    parser.add_argument("--out", required=True,
                        help="output weights JSON path (relative paths "
                             "resolve to the repo root, not the cwd)")
    parser.add_argument("--min-rows", type=int, default=10)
    args = parser.parse_args(argv)
    from app.db.database import get_session_factory, repo_root

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = repo_root() / out_path
    db = get_session_factory()()
    try:
        weights = train(db, min_rows=args.min_rows)
    except TrainingError as e:
        print(f"training failed: {e}")
        return 1
    finally:
        db.close()
    path = write_weights(weights, out_path)
    print(json.dumps({"written": str(path),
                      "rows": weights["meta"]["rows"],
                      "features": len(weights["features"]),
                      "positive": weights["meta"]["positive"],
                      "negative": weights["meta"]["negative"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
