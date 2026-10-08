"""Cheap visual interest (S14/V4-preview): luma motion + brightness.

Samples ~1fps grayscale thumbnails through ffmpeg and scores frame-to-frame
change. Deterministic, CPU-trivial, no model weights. Only ever runs on
finalist windows (see find_moments), never on full videos.
"""

import structlog
from pathlib import Path

from app.services import ffmpeg_service as ff

log = structlog.get_logger()


def sample_luma(media: Path, start: float, duration: float, fps: int = 1,
               width: int = 64, roots: list[Path] | None = None) -> list:
    """Return luma frames as flat lists of 0..255 ints (binary pipe)."""
    import shutil
    import subprocess

    info = ff.probe(media, roots)
    vw, vh = max(info.get("width", 0), 1), max(info.get("height", 0), 1)
    h = max((width * vh // vw) // 2 * 2, 2)
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found on PATH")
    proc = subprocess.run(
        [exe, "-y", "-v", "error",
         "-ss", str(max(start, 0.0)), "-t", str(max(duration, 0.1)),
         "-i", str(ff.resolve_data_path(media, roots)),
         "-vf", f"fps={fps},scale={width}:-2",
         "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"],
        capture_output=True, shell=False, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError("frame sampling failed: "
                           f"{proc.stderr.decode()[-300:]}")
    frame_bytes = width * h
    buf = proc.stdout
    frames = []
    for i in range(0, len(buf) - frame_bytes + 1, frame_bytes):
        frames.append(list(buf[i:i + frame_bytes]))
    log.info("frames_sampled", count=len(frames), width=width, height=h)
    return frames


def visual_interest(frames: list[list[int]]) -> float:
    """0..1: motion change blended with mid-brightness preference."""
    if len(frames) < 2:
        return 0.0
    diffs = 0
    total = 0
    for prev, cur in zip(frames, frames[1:]):
        for a, b in zip(prev, cur):
            diffs += abs(a - b)
            total += 1
    motion = (diffs / total) / 255.0 if total else 0.0
    mean = sum(sum(f) for f in frames) / max(
        sum(len(f) for f in frames), 1) / 255.0
    brightness = max(0.0, 1.0 - abs(mean - 0.5) * 2.0)
    return round(min(max(0.6 * min(motion * 4.0, 1.0) + 0.4 * brightness,
                       0.0), 1.0), 3)


def score_window_visual(media: Path, start: float, end: float,
                        fps: int = 1,
                        roots: list[Path] | None = None) -> float:
    frames = sample_luma(media, start, end - start, fps=fps, roots=roots)
    return visual_interest(frames)
