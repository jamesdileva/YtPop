"""Shared render fixtures: lavfi media + words-bearing transcripts."""

import json
from pathlib import Path

from app.db import models
from app.services import ffmpeg_service as ff


def gen_clip(path: Path, duration: int = 5, freq: int = 440) -> Path:
    ff.run_cmd("ffmpeg", [
        "-y", "-f", "lavfi", "-i",
        f"testsrc2=size=320x240:rate=15:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(path),
    ])
    return path


def words_for(duration: float, step: float = 0.5) -> list[dict]:
    words, t, i = [], 0.0, 0
    while t < duration:
        words.append({"start": round(t, 3),
                      "end": round(min(t + step, duration), 3),
                      "word": f" word{i}", "probability": 0.99})
        t += step
        i += 1
    return words


def seed_episode(db, tmp_path: Path, n_clips: int = 3,
                 clip_dur: int = 5) -> int:
    """Sources + media + transcripts + APPROVED moments + episode w/ cards."""
    ep = models.Episode(title="Render fixture", target_duration=1200.0)
    db.add(ep)
    db.flush()
    db.add(models.EpisodeSegment(
        episode_id=ep.id, moment_id=None, sequence=0, duration=2.0,
        transition_type="cut", context_text="Intro card"))
    for i in range(n_clips):
        media = gen_clip(tmp_path / f"clip{i}.mp4", clip_dur, 440 + i * 40)
        src = models.Source(provider="youtube", external_id=f"r{i}",
                            url="", title=f"Clip {i}")
        db.add(src)
        db.flush()
        db.add(models.MediaAsset(source_id=src.id, kind="raw",
                                 path=str(media), duration=float(clip_dur)))
        segs = [{"start": 0.0, "end": float(clip_dur),
                 "text": "caption test",
                 "words": words_for(float(clip_dur))}]
        db.add(models.Transcript(
            source_id=src.id, language="en", model="test",
            text="caption test", segments_json=json.dumps(segs),
            audio_sha256="x"))
        moment = models.Moment(
            source_id=src.id, start_time=0.0, end_time=float(clip_dur),
            transcript_excerpt="caption test", final_score=80.0,
            status="APPROVED")
        db.add(moment)
        db.flush()
        db.add(models.EpisodeSegment(
            episode_id=ep.id, moment_id=moment.id,
            sequence=i + 1, duration=float(clip_dur),
            transition_type="cut"))
    db.add(models.EpisodeSegment(
        episode_id=ep.id, moment_id=None,
        sequence=n_clips + 1, duration=2.0,
        transition_type="fade", context_text="Outro card"))
    db.commit()
    return ep.id
