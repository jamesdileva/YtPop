"""Real-model test: tiny faster-whisper on SAPI-synthesized speech.

Skips when Windows speech synthesis is unavailable. Asserts the segment
schema (incl. word timings) and monotonic timings — not exact wording,
since tiny-model phrasing may vary.
"""

import subprocess
from pathlib import Path

import pytest

from app.services.whisper_service import WhisperService


def synth_speech(wav: Path) -> bool:
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate = -2; "
        f"$s.SetOutputToWaveFile('{wav}'); "
        "$s.Speak('Hello world. This is a transcription test.'); "
        "$s.Dispose()"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       check=True, timeout=120, capture_output=True)
    except Exception:
        return False
    if not (wav.is_file() and wav.stat().st_size > 0):
        return False
    # SAPI writes 22050Hz; the service requires the 16kHz wav that ingestion
    # produces, so resample here the same way extract_audio() does.
    try:
        from app.services import ffmpeg_service as ff

        resampled = wav.with_suffix(".16k.wav")
        ff.extract_audio(wav, resampled)
        resampled.replace(wav)
    except Exception:
        return False
    return wav.is_file() and wav.stat().st_size > 0


def test_tiny_model_schema_and_word_timings(tmp_path):
    wav = tmp_path / "speech.wav"
    if not synth_speech(wav):
        pytest.skip("SAPI speech synthesis unavailable")
    result = WhisperService("tiny", "cpu", "int8").transcribe(wav)
    assert result["language"] == "en"
    assert len(result["segments"]) >= 1
    assert len(result["text"]) > 0
    prev_end = -1.0
    words_total = 0
    for seg in result["segments"]:
        assert set(seg) >= {"start", "end", "text", "words"}
        assert 0 <= seg["start"] <= seg["end"]
        assert seg["start"] >= prev_end - 0.01
        prev_end = seg["end"]
        for w in seg["words"]:
            assert set(w) >= {"start", "end", "word"}
            assert seg["start"] - 0.5 <= w["start"] <= w["end"] <= seg["end"] + 0.5
            words_total += 1
    assert words_total >= 1, "word timings must be preserved"


def test_missing_file_fails_safely(tmp_path):
    from app.services.whisper_service import TranscriptionError

    with pytest.raises(TranscriptionError, match="not found"):
        WhisperService("tiny").transcribe(tmp_path / "nope.wav")
