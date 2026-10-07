"""Rendering (S9): episode timeline → mp4 (+ ASS sidecar, burn-in, QA).

Synchronous in-request render (S13 adds background orchestration).
Every render records a Render row + RENDER job row; failures surface the
ffmpeg error and stay retryable via a fresh POST /episodes/{id}/render.
"""

import json
import structlog
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.db import models
from app.services import ffmpeg_service as ff

log = structlog.get_logger()


class RenderError(RuntimeError):
    pass


DEFAULT_PRESETS: dict = {
    "preview_720p": {
        "width": 1280, "height": 720, "fps": 30, "vcodec": "libx264",
        "x264_preset": "ultrafast", "crf": 23, "acodec": "aac",
        "audio_bitrate": "128k", "caption_style": "standard",
        "burn_captions": True,
    }
}

# name → (fontsize, primary, bold, alignment)
# colors are ASS &HAABBGGRR
CAPTION_STYLES = {
    "standard": (56, "&H00FFFFFF", 0, 2),
    "bold": (64, "&H00FFFFFF", -1, 2),
    "highlight": (60, "&H0000FFFF", -1, 2),
    "vertical": (48, "&H00FFFFFF", 0, 8),
    "minimal": (44, "&H99FFFFFF", 0, 2),
}

CARD_COLOR = "0x1a1a2e"


def load_presets(path: str | Path | None = None) -> dict:
    presets = deepcopy(DEFAULT_PRESETS)
    if path is None:
        from app.db.database import repo_root

        candidate = repo_root() / "configs" / "render.yaml"
    else:
        candidate = Path(path)
    if candidate.is_file():
        with open(candidate, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        for name, preset in (loaded.get("presets") or {}).items():
            merged = deepcopy(DEFAULT_PRESETS["preview_720p"])
            merged.update(preset or {})
            presets[name] = merged
    return presets


def ass_time(seconds: float) -> str:
    seconds = max(seconds, 0.0)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _escape_ass(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(events: list[dict], style: str = "standard") -> str:
    """events: [{start, end, text}] in final-timeline seconds."""
    size, primary, bold, align = CAPTION_STYLES.get(
        style, CAPTION_STYLES["standard"])
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1280\nPlayResY: 720\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, "
        "SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: YtPop,Arial,{size},{primary},&H000019FF,&H80000000,"
        f"&H80000000,{bold},0,0,0,100,100,0,0,1,2,0,{align},20,20,30,1\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
    )
    lines = [
        f"Dialogue: 0,{ass_time(e['start'])},{ass_time(e['end'])},"
        f"YtPop,,0,0,0,,{_escape_ass(e['text'])}"
        for e in events
    ]
    return header + "\n".join(lines) + "\n"


def words_to_events(words: list[dict], per_event: int = 7) -> list[dict]:
    """Group word timings into readable caption events.

    Card titles (flagged) always stand alone — never merged with clip words.
    """
    events = []
    run: list[dict] = []

    def flush(run: list[dict]) -> None:
        for i in range(0, len(run), per_event):
            chunk = run[i:i + per_event]
            text = "".join(
                w["word"] if w["word"].startswith(" ") else " " + w["word"]
                for w in chunk
            ).strip()
            if text:
                events.append({
                    "start": chunk[0]["start"], "end": chunk[-1]["end"],
                    "text": text,
                })

    for w in words:
        if w.get("card"):
            flush(run)
            run = []
            events.append({"start": w["start"], "end": w["end"],
                           "text": w["word"].strip()})
        else:
            run.append(w)
    flush(run)
    return sorted(events, key=lambda e: e["start"])


def _card_text(seg, title: str) -> str:
    return (seg.context_text or seg.commentary_text or title).strip()


def _probe_fps(path: Path) -> float:
    """Read container/video-stream fps via ffprobe."""
    import json as _json

    out = ff.run_cmd("ffprobe", [
        "-v", "quiet", "-print_format", "json",
        "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
        str(path),
    ])
    rate = (_json.loads(out).get("streams") or [{}])[0].get("r_frame_rate", "0/1")
    num, _, den = rate.partition("/")
    try:
        return float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0


def render_episode(
    db: Session, episode_id: int, preset_name: str = "preview_720p",
    roots: list[Path] | None = None,
) -> dict:
    presets = load_presets()
    if preset_name not in presets:
        raise RenderError(
            f"unknown preset {preset_name!r}, one of {sorted(presets)}")
    preset = presets[preset_name]
    W, H, FPS = preset["width"], preset["height"], preset["fps"]
    base = (roots or [ff.repo_data_dir()])[0]

    ep = db.get(models.Episode, episode_id)
    if ep is None:
        raise RenderError(f"episode not found: {episode_id}")

    render = models.Render(
        episode_id=episode_id, preset=preset_name,
        resolution=f"{W}x{H}", fps=FPS, codec=preset["vcodec"],
        status="RUNNING",
    )
    db.add(render)
    db.flush()
    job = models.Job(
        type="RENDER", status="RUNNING", priority=30,
        payload_json=json.dumps({"episode_id": episode_id,
                                 "preset": preset_name}),
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()
    out = ff.resolve_data_path(Path("renders") / f"{render.id}.mp4", [base])
    out.parent.mkdir(parents=True, exist_ok=True)
    ass_path = ff.resolve_data_path(
        Path("captions") / f"render_{render.id}.ass", [base])
    ass_path.parent.mkdir(parents=True, exist_ok=True)

    def fail(message: str) -> RenderError:
        render.status = "FAILED"
        render.error = message[:2000]
        job.status = "FAILED"
        job.error = message[:2000]
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return RenderError(message)

    try:
        segs = (
            db.query(models.EpisodeSegment).filter_by(episode_id=episode_id)
            .order_by(models.EpisodeSegment.sequence.asc()).all()
        )
        if not segs:
            raise RenderError(f"episode {episode_id} has no segments")
        # --- inputs (durations + caption timing) ---
        args: list[str] = ["-y"]
        takes: list[float] = []
        caption_words: list[dict] = []
        offset = 0.0
        for seg in segs:
            if seg.moment_id is None:
                dur = round(float(seg.duration), 3)
                args += ["-f", "lavfi", "-i",
                         f"color=c={CARD_COLOR}:s={W}x{H}:r={FPS}:d={dur}",
                         "-f", "lavfi", "-i",
                         f"aevalsrc=0:d={dur}:s=48000"]
                takes.append(dur)
                # card titles ride along as caption events (no drawtext:
                # fontfile drive-letter escaping is fragile across builds)
                caption_words.append({
                    "start": offset, "end": offset + dur,
                    "word": " " + _card_text(seg, ep.title), "card": True,
                })
                offset += dur
                continue
            moment = db.get(models.Moment, seg.moment_id)
            if moment is None:
                raise RenderError(f"segment {seg.id} references "
                                  f"missing moment {seg.moment_id}")
            media = _segment_media(db, seg.moment_id)
            avail = float(moment.end_time) - float(moment.start_time)
            take = round(min(float(seg.duration), avail), 3)
            if take <= 0:
                raise RenderError(f"segment {seg.id} has zero duration")
            args += ["-ss", str(float(moment.start_time)), "-t", str(take),
                     "-i", str(media)]
            takes.append(take)
            # caption words in moment range, shifted to final timeline
            for w in _transcript_words(db, moment):
                if moment.start_time <= w["start"] < moment.start_time + take:
                    caption_words.append({
                        "start": round(offset + (w["start"] - moment.start_time), 3),
                        "end": round(offset + (w["end"] - moment.start_time), 3),
                        "word": w["word"],
                    })
            offset += take

        # --- filter graph (input indices assigned in segment order) ---
        # clip segments contribute 1 input; card segments contribute 2
        filters = []
        in_cursor = 0
        for idx, seg in enumerate(segs):
            if seg.moment_id is None:
                filters.append(f"[{in_cursor}:v]setsar=1,fps={FPS}[v{idx}]")
                filters.append(f"[{in_cursor + 1}:a]aresample=48000,"
                               f"aformat=channel_layouts=stereo[a{idx}]")
                in_cursor += 2
            else:
                filters.append(
                    f"[{in_cursor}:v]scale={W}:{H}:force_original_aspect_"
                    f"ratio=increase,crop={W}:{H},setsar=1,fps={FPS}[v{idx}]")
                filters.append(f"[{in_cursor}:a]aresample=48000,"
                               f"aformat=channel_layouts=stereo[a{idx}]")
                in_cursor += 1
        n = len(segs)
        streams = "".join(f"[v{idx}][a{idx}]" for idx in range(n))
        filters.append(f"{streams}concat=n={n}:v=1:a=1[vcat][acat]")
        filters.append("[acat]loudnorm=I=-16:TP=-1.5:LRA=11[aloud]")

        events = words_to_events(caption_words)
        ass_text = build_ass(events, str(preset["caption_style"]))
        ass_path.write_text(ass_text, encoding="utf-8")
        v_final = "[vcat]"
        if preset["burn_captions"] and events:
            # NOTE: this FFmpeg build misparses drive-letter colons inside
            # filter args (any absolute Windows path fails). Run with
            # cwd=base and reference the ASS file relatively.
            ass_rel = ass_path.relative_to(base).as_posix()
            filters.append(f"[vcat]subtitles={ass_rel}[vout]")
            v_final = "[vout]"
        filters_str = ";".join(filters)
        cmd = args + [
            "-filter_complex", filters_str,
            "-map", v_final, "-map", "[aloud]",
            "-r", str(FPS),
            "-c:v", preset["vcodec"], "-preset", preset["x264_preset"],
            "-crf", str(preset["crf"]), "-pix_fmt", "yuv420p",
            "-c:a", preset["acodec"], "-b:a", preset["audio_bitrate"],
            "-ar", "48000", "-movflags", "+faststart",
            str(out),
        ]
        ff.run_cmd("ffmpeg", cmd, timeout=900, cwd=base)
        expected = round(sum(takes), 3)
        qa = qa_render(str(out), preset, expected, ass_path)
        if not qa["ok"]:
            raise RenderError(f"render QA failed: {qa['failed']}")
        render.path = str(out)
        render.status = "COMPLETED"
        render.completed_at = datetime.now(timezone.utc)
        job.status = "COMPLETED"
        job.progress = 1.0
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        log.info("render_done", render_id=render.id, preset=preset_name,
                 duration=qa["duration"])
        return {"render_id": render.id, "path": str(out),
                "preset": preset_name, "qa": qa}
    except RenderError as e:
        # rows exist from here on (episode/preset validated before) — record
        raise fail(str(e)) from e
    except Exception as e:
        raise fail(f"render failed: {e}") from e


def _segment_media(db: Session, moment_id: int) -> Path:
    moment = db.get(models.Moment, moment_id)
    assert moment is not None
    for kind in ("normalized", "raw"):
        asset = (
            db.query(models.MediaAsset)
            .filter_by(source_id=moment.source_id, kind=kind)
            .order_by(models.MediaAsset.id.desc()).first()
        )
        if asset is not None and Path(asset.path).is_file():
            return Path(asset.path)
    raise RenderError(f"moment {moment_id} has no playable media — ingest first")


def _transcript_words(db: Session, moment: models.Moment) -> list[dict]:
    tr = (
        db.query(models.Transcript).filter_by(source_id=moment.source_id)
        .order_by(models.Transcript.id.desc()).first()
    )
    if tr is None:
        return []
    words: list[dict] = []
    for seg in json.loads(tr.segments_json):
        words.extend(seg.get("words", []) or [])
    return words


def qa_render(path: str | Path, preset: dict, expected_duration: float,
              captions_path: str | Path | None = None) -> dict:
    """Render QA: exists, duration, a+v streams, res/fps, captions, clean decode."""
    checks: dict[str, bool] = {}
    failed: list[str] = []
    target = Path(path)
    checks["exists"] = target.is_file()
    info: dict = {}
    if checks["exists"]:
        try:
            info = ff.probe(target, [target.parent])
        except Exception:
            info = {}
    dur = float(info.get("duration", 0.0) or 0.0)
    checks["duration_positive"] = dur > 0
    checks["duration_matches"] = abs(dur - expected_duration) <= max(
        1.0, expected_duration * 0.05)
    checks["has_video"] = bool(info.get("has_video"))
    checks["has_audio"] = bool(info.get("has_audio"))
    checks["resolution"] = (
        info.get("width") == preset["width"]
        and info.get("height") == preset["height"])
    try:
        fps = _probe_fps(target) if checks["exists"] else 0.0
    except Exception:
        fps = 0.0
    checks["fps"] = abs(fps - float(preset["fps"])) < 1.0
    if captions_path is not None:
        cap = Path(captions_path)
        checks["captions_present"] = cap.is_file() and cap.stat().st_size > 0
    if checks["exists"]:
        try:
            err = ff.run_cmd("ffmpeg", ["-v", "error", "-i", str(target),
                                        "-f", "null", "-"])
            checks["clean_decode"] = True
        except Exception:
            checks["clean_decode"] = False
    else:
        checks["clean_decode"] = False
    failed = [k for k, v in checks.items() if not v]
    return {"ok": not failed, "failed": failed, "checks": checks,
            "duration": round(dur, 3),
            "resolution": f"{info.get('width', 0)}x{info.get('height', 0)}",
            "fps": round(fps, 2)}
