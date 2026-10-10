"""Scene detection (S4/D10): ffmpeg scene-change scores -> cut timestamps.

Cheap-first and dependency-free: the bundled ffmpeg computes per-frame scene
scores (`select=scene` yields the frames where the score is non-zero), and we
parse the `metadata=print` output. No PySceneDetect/torch, so the packaged
freeze stays lean and the result is deterministic.
"""

import re
import structlog
from pathlib import Path

from app.services import ffmpeg_service as ff

log = structlog.get_logger()

_FRAME_RE = re.compile(r"^frame:\d+\s+pts:\d+\s+pts_time:([0-9.]+)\s*$")
_SCORE_RE = re.compile(r"^lavfi\.scene_score=([0-9.]+)\s*$")


class SceneError(RuntimeError):
    pass


def parse_scene_scores(output: str) -> list[dict]:
    """Parse `metadata=print` stdout into [{start, score}] in time order."""
    cuts: list[dict] = []
    pending_time: float | None = None
    for line in output.splitlines():
        m = _FRAME_RE.match(line)
        if m:
            pending_time = float(m.group(1))
            continue
        m = _SCORE_RE.match(line)
        if m and pending_time is not None:
            cuts.append({"start": round(pending_time, 3),
                         "score": round(float(m.group(1)), 4)})
            pending_time = None
    return sorted(cuts, key=lambda c: c["start"])


def detect_scenes(
    media: Path, roots: list[Path] | None = None,
    threshold: float = 0.35, max_scenes: int = 300,
) -> list[dict]:
    """Return hard cuts (score >= threshold) as [{start, score}]."""
    target = ff.resolve_data_path(media, roots)
    if not target.is_file():
        raise SceneError(f"media file not found: {target}")
    out = ff.run_cmd("ffmpeg", [
        "-hide_banner", "-v", "error",
        "-i", str(target),
        "-vf", "select=scene,metadata=print:file=-",
        "-f", "null", "-",
    ], timeout=600)
    cuts = [c for c in parse_scene_scores(out) if c["score"] >= threshold]
    dropped = len(parse_scene_scores(out)) - len(cuts)
    if len(cuts) > max_scenes:
        cuts = cuts[:max_scenes]
    log.info("scenes_detected", path=str(target), cuts=len(cuts),
             below_threshold=dropped)
    return cuts
