"""FFmpeg adapter (S4). Arg-arrays only — never shell-concat.

Every filesystem path crossing this boundary must resolve under one of the
allowed roots (default: repo `data/`). Anything else raises PathTraversalError.
"""

import json
import shutil
import structlog
import subprocess
from pathlib import Path

log = structlog.get_logger()


class FFmpegError(RuntimeError):
    pass


class PathTraversalError(ValueError):
    pass


def repo_data_dir() -> Path:
    # Single source of truth for the repo root lives in app.db.database.
    from app.db.database import repo_root

    return repo_root() / "data"


def resolve_data_path(raw: str | Path, roots: list[Path] | None = None) -> Path:
    """Resolve `raw` and require it to sit under one of `roots`."""
    allowed = roots or [repo_data_dir()]
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = allowed[0] / candidate
    resolved = candidate.resolve()
    for root in allowed:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise PathTraversalError(f"path escapes allowed roots: {raw}")


def _binary(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise FFmpegError(f"{name} not found on PATH")
    return found


def run_cmd(binary: str, args: list[str], timeout: int = 300) -> str:
    """Run `[binary, *args]` with shell=False. Returns stdout tail context."""
    exe = _binary(binary)
    log.info("ffmpeg_run", exe=exe, args=args)
    try:
        proc = subprocess.run(
            [exe, *args], capture_output=True, text=True,
            shell=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise FFmpegError(f"{binary} timed out: {args[:3]}") from e
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-800:]
        raise FFmpegError(f"{binary} failed (rc={proc.returncode}): {tail}")
    return proc.stdout


def probe(path: str | Path, roots: list[Path] | None = None) -> dict:
    """ffprobe a media file → normalized stream summary."""
    target = resolve_data_path(path, roots)
    if not target.is_file():
        raise FFmpegError(f"media file not found: {target}")
    out = run_cmd("ffprobe", [
        "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(target),
    ])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as e:
        raise FFmpegError(f"ffprobe returned invalid json for {target}") from e
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    try:
        duration = float(data.get("format", {}).get("duration", 0.0) or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "path": str(target),
        "duration": duration,
        "width": int(video.get("width", 0) or 0),
        "height": int(video.get("height", 0) or 0),
        "vcodec": str(video.get("codec_name", "")),
        "acodec": str(audio.get("codec_name", "")),
        "has_video": bool(video),
        "has_audio": bool(audio),
        "stream_count": len(streams),
    }


def normalize(
    src: str | Path, dst: str | Path,
    target_height: int = 720, roots: list[Path] | None = None,
) -> Path:
    """Transcode to a mezzanine mp4 (h264 + aac). Returns output path."""
    src_p = resolve_data_path(src, roots)
    dst_p = resolve_data_path(dst, roots)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    run_cmd("ffmpeg", [
        "-y", "-i", str(src_p),
        "-vf", f"scale=-2:{target_height}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "48000", "-ac", "2",
        str(dst_p),
    ])
    return dst_p


def extract_audio(
    src: str | Path, dst: str | Path, roots: list[Path] | None = None
) -> Path:
    """Extract 16kHz mono wav for transcription (S5 input)."""
    src_p = resolve_data_path(src, roots)
    dst_p = resolve_data_path(dst, roots)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    run_cmd("ffmpeg", [
        "-y", "-i", str(src_p),
        "-vn", "-ar", "16000", "-ac", "1",
        "-c:a", "pcm_s16le", str(dst_p),
    ])
    return dst_p


def extract_thumbnail(
    src: str | Path, dst: str | Path, at_seconds: float = 0.5,
    roots: list[Path] | None = None,
) -> Path:
    """Grab a single jpg frame."""
    src_p = resolve_data_path(src, roots)
    dst_p = resolve_data_path(dst, roots)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    run_cmd("ffmpeg", [
        "-y", "-ss", str(at_seconds), "-i", str(src_p),
        "-frames:v", "1", "-q:v", "3", str(dst_p),
    ])
    return dst_p
