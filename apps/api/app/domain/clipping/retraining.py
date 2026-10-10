"""Automatic ranker retraining (D13): policy-gated, validated, audited.

Cadence is driven by the scheduler job `RETRAIN` (configs/default.yaml
`retraining:`), and can also be triggered by hand. The design is
conservative on purpose: a bad weights file silently degrades every
find-moments call, so a run only lands when it passes a holdout check and,
optionally, beats the weights currently in use.

Sequence per run:
  1. policy gate   -> enough NEW labels since the last accepted run, and the
                      minimum interval elapsed (force bypasses both)
  2. split + train -> deterministic every-4th holdout
  3. validate      -> holdout accuracy/AUC must clear the floors
  4. promote       -> backup the old file, write the new one
  5. audit         -> every decision (including refusals) is a ranker_runs row
"""

import json
import shutil
import structlog
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.domain.clipping import training

log = structlog.get_logger()

RETRAIN_TYPE = "RETRAIN"


class RetrainError(RuntimeError):
    pass


def _cfg() -> dict:
    import yaml

    from app.db.database import repo_root

    data = {}
    path = repo_root() / "configs" / "default.yaml"
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    return data.get("retraining") or {}


DEFAULT_CFG = {
    "enabled": True,
    "min_new_labels": 20,
    "min_interval_hours": 24,
    "min_rows": 10,
    "min_holdout_accuracy": 0.6,
    "min_holdout_auc": 0.6,
    "require_improvement": True,
    "output": "data/models/ranker.json",
}


def _config(cfg: dict | None) -> dict:
    merged = dict(DEFAULT_CFG)
    merged.update(cfg if cfg is not None else _cfg())
    return merged


def state(db: Session, cfg: dict | None = None) -> dict:
    """Current weights, last accepted run, label count, next-due time."""
    c = _config(cfg)
    labels = training.build_dataset(db)[1]
    last = (
        db.query(models.RankerRun)
        .order_by(models.RankerRun.id.desc()).first()
    )
    accepted = (
        db.query(models.RankerRun)
        .filter_by(accepted=True)
        .order_by(models.RankerRun.id.desc()).first()
    )
    from app.db.database import repo_root

    weights_path = Path(c["output"])
    if not weights_path.is_absolute():
        weights_path = repo_root() / weights_path
    return {
        "config": c,
        "labels": len(labels),
        "weights_file": str(weights_path),
        "weights_present": weights_path.is_file(),
        "last_run": _run_row(last),
        "last_accepted": _run_row(accepted),
        "learning_enabled": _learning_enabled(),
    }


def _run_row(run: models.RankerRun | None) -> dict | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "trained_at": run.trained_at.isoformat() if run.trained_at else None,
        "rows": run.rows,
        "new_labels": run.new_labels,
        "accuracy": run.holdout_accuracy,
        "auc": run.holdout_auc,
        "accepted": run.accepted,
        "reason": run.reason,
        "forced": run.forced,
    }


def _learning_enabled() -> bool:
    """Is learned_ranking actually applied by find-moments?"""
    import yaml

    from app.db.database import repo_root

    path = repo_root() / "configs" / "scoring.yaml"
    if not path.is_file():
        return False
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return bool((data.get("learned_ranking") or {}).get("enabled"))


def _utc(dt) -> "datetime":
    from datetime import datetime, timezone

    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _new_labels_since(db: Session, run: models.RankerRun | None) -> int:
    """Feedback rows that are NEW since the given run evaluated the dataset.

    ranker_runs stores the label counts it saw, so "new" is the current
    labelled count minus what that run saw. Falling back to total for the
    first run (no run yet) keeps the gate conservative.
    """
    current = len(training.build_dataset(db)[1])
    if run is None:
        return current
    return max(current - run.rows, 0)


def maybe_retrain(db: Session, force: bool = False,
                  cfg: dict | None = None) -> dict:
    """Run the cadence policy. Returns the audit summary (never writes a
    weights file unless the new model validates)."""
    c = _config(cfg)
    rows_feats, labels, decisions = training.build_dataset(db)
    last = (
        db.query(models.RankerRun)
        .order_by(models.RankerRun.id.desc()).first()
    )
    new_labels = _new_labels_since(db, last)

    def refuse(reason: str, **extra) -> dict:
        _audit(db, rows=len(labels), positive=int(sum(labels)),
               negative=int(len(labels) - sum(labels)),
               new_labels=new_labels, accuracy=0.0, auc=0.5,
               accepted=False, reason=reason, weights_path="", forced=force)
        db.commit()
        log.info("retrain_refused", reason=reason, new_labels=new_labels)
        return {"accepted": False, "reason": reason,
                "labels": len(labels), "new_labels": new_labels, **extra}

    if not c["enabled"] and not force:
        return refuse("retraining disabled in config")

    if len(labels) < int(c["min_rows"]):
        return refuse(
            f"only {len(labels)} labelled rows (need {c['min_rows']})")

    if len(set(labels)) < 2:
        return refuse("need both approved and rejected labels")

    if not force:
        if new_labels < int(c["min_new_labels"]):
            return refuse(
                f"only {new_labels} new labels since last run "
                f"(need {c['min_new_labels']})")
        from datetime import datetime, timezone, timedelta

        last_time = (
            _utc(db.query(models.RankerRun)
                 .filter_by(accepted=True)
                 .order_by(models.RankerRun.id.desc()).first().trained_at)
            if db.query(models.RankerRun)
            .filter_by(accepted=True).count() else None
        )
        if last_time is not None:
            age = datetime.now(timezone.utc) - last_time
            need = timedelta(hours=float(c["min_interval_hours"]))
            if age < need:
                hours_left = round((need - age).total_seconds() / 3600, 1)
                return refuse(
                    f"last accepted run was {round(age.total_seconds() / 3600, 1)}h "
                    f"ago (need {c['min_interval_hours']}h; {hours_left}h left)",
                    retry_in_hours=hours_left)

    train_idx, test_idx = training.split_indices(len(labels), labels=labels)
    if not train_idx or not test_idx:
        return refuse("dataset too small for a holdout split")
    if len({labels[i] for i in train_idx}) < 2:
        return refuse("training split lacks both classes")

    train_rows = [rows_feats[i] for i in train_idx]
    train_labels = [labels[i] for i in train_idx]
    test_rows = [rows_feats[i] for i in test_idx]
    test_labels = [labels[i] for i in test_idx]

    try:
        weights = training.train_from(train_rows, train_labels, decisions)
    except training.TrainingError as e:
        return refuse(f"training failed: {e}")

    holdout = training.evaluate(weights, test_rows, test_labels)
    accuracy, auc = holdout["accuracy"], holdout["auc"]
    if accuracy < float(c["min_holdout_accuracy"]) or auc < float(c["min_holdout_auc"]):
        return refuse(
            f"holdout floors not met (accuracy {accuracy} >= "
            f"{c['min_holdout_accuracy']}, auc {auc} >= {c['min_holdout_auc']})",
            holdout=holdout,
        )

    from app.db.database import repo_root

    out_path = Path(c["output"])
    if not out_path.is_absolute():
        out_path = repo_root() / out_path

    if c["require_improvement"] and out_path.is_file():
        current = training.json.loads(out_path.read_text(encoding="utf-8"))
        cur_acc = training.evaluate(current, test_rows, test_labels)["accuracy"]
        if accuracy <= cur_acc:
            return refuse(
                f"no improvement over current weights "
                f"({accuracy} <= {cur_acc})", holdout=holdout,
                current_accuracy=cur_acc)

    if out_path.is_file():
        backup = out_path.with_suffix(".json.bak")
        shutil.copy2(out_path, backup)
        log.info("weights_backed_up", backup=str(backup))
    training.write_weights(weights, out_path)

    _audit(db, rows=len(train_rows) + len(test_rows),
           positive=int(sum(labels)), negative=int(len(labels) - sum(labels)),
           new_labels=new_labels, accuracy=accuracy, auc=auc,
           accepted=True, reason="validated and promoted",
           weights_path=str(out_path), forced=force)
    db.commit()
    log.info("retrain_accepted", path=str(out_path), accuracy=accuracy, auc=auc)
    return {
        "accepted": True,
        "weights_path": str(out_path),
        "holdout": holdout,
        "labels": len(labels),
        "new_labels": new_labels,
        "learning_enabled": _learning_enabled(),
        "note": None if _learning_enabled() else
                "weights written; set learned_ranking.enabled=true in "
                "configs/scoring.yaml for find_moments to apply them",
    }


def _audit(db: Session, *, rows: int, positive: int, negative: int,
           new_labels: int, accuracy: float, auc: float, accepted: bool,
           reason: str, weights_path: str, forced: bool) -> models.RankerRun:
    run = models.RankerRun(
        rows=rows, positive=positive, negative=negative,
        new_labels=new_labels, holdout_accuracy=accuracy, holdout_auc=auc,
        accepted=accepted, reason=reason[:1000],
        weights_path=weights_path, forced=forced,
    )
    db.add(run)
    db.flush()
    return run
