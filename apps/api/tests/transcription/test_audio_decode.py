"""WhisperService decodes 16k mono PCM with the stdlib (no `av`)."""

import wave

import numpy as np
import pytest

from app.services.whisper_service import (
    TranscriptionError, WhisperService, load_audio)


def _wav(path, seconds=1.0, rate=16000, channels=1, width=2, tone=True):
    frames = int(seconds * rate)
    if tone and width == 2:
        import math

        data = b"".join(
            int(12000 * math.sin(2 * math.pi * 440 * i / rate)).to_bytes(
                2, "little", signed=True)
            for i in range(frames * channels))
    else:
        data = b"\x00" * (frames * channels * width)
    with wave.open(str(path), "wb") as h:
        h.setnchannels(channels)
        h.setsampwidth(width)
        h.setframerate(rate)
        h.writeframes(data)
    return path


def test_load_audio_mono_16k(tmp_path):
    p = _wav(tmp_path / "a.wav", seconds=0.5)
    audio = load_audio(p)
    assert audio.dtype.name == "float32"
    assert audio.size == 8000
    assert -1.0 <= float(audio.max()) <= 1.0


def test_load_audio_stereo_is_downmixed(tmp_path):
    p = _wav(tmp_path / "s.wav", seconds=0.25, channels=2)
    audio = load_audio(p)
    assert audio.size == 4000  # 0.25s of mono after downmix


def test_load_audio_rejects_bad_wav(tmp_path):
    with pytest.raises(TranscriptionError, match="16-bit"):
        load_audio(_wav(tmp_path / "w8.wav", width=1))
    with pytest.raises(TranscriptionError, match="16kHz"):
        load_audio(_wav(tmp_path / "r44.wav", rate=44100))
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not a wav")
    with pytest.raises(TranscriptionError, match="could not read"):
        load_audio(bad)


def test_load_audio_rejects_empty_samples(tmp_path):
    p = _wav(tmp_path / "e.wav", seconds=0.0)
    with pytest.raises(TranscriptionError, match="no samples"):
        load_audio(p)


def test_av_shim_installed_when_pyav_missing(monkeypatch):
    """The trimmed freeze excludes PyAV; faster-whisper still must import."""
    import sys

    from app.services import whisper_service
    from app.services.whisper_service import TranscriptionError

    saved = sys.modules.pop("av", None)
    try:
        sys.modules["av"] = None  # forces `import av` to raise ImportError
        monkeypatch.delenv("AV_DISABLE", raising=False)
        whisper_service._ensure_av_shim()
        shim = sys.modules["av"]
        assert shim is not None
        with pytest.raises(TranscriptionError, match="PyAV is not installed"):
            shim.audio.resampler.AudioResampler  # noqa: B018
    finally:
        sys.modules.pop("av", None)
        if saved is not None:
            sys.modules["av"] = saved


def test_av_shim_keeps_real_pyav(monkeypatch):
    """When PyAV is installed the shim must not replace it."""
    import sys

    from app.services import whisper_service

    try:
        import av  # noqa: F401
    except ImportError:
        pytest.skip("PyAV not installed")
    whisper_service._ensure_av_shim()
    assert "av" in sys.modules
    assert not sys.modules["av"].__dict__.get("_is_shim")


def test_transcribe_uses_array_decode(monkeypatch, tmp_path):
    """transcribe() feeds the decoded array to the model (no `av` path)."""
    seen = {}

    class FakeModel:
        def transcribe(self, audio, language=None, word_timestamps=False):
            seen["type"] = type(audio).__name__
            seen["kwargs"] = {"language": language,
                              "word_timestamps": word_timestamps}

            class Seg:
                start, end, text, avg_logprob = 0.0, 1.0, " hi", -0.1
                words = []

            return [Seg()], type("Info", (), {"language": "en"})()

    svc = WhisperService("tiny")
    svc._model = FakeModel()
    out = svc.transcribe(_wav(tmp_path / "t.wav"))
    assert seen["type"] == "ndarray"
    assert seen["kwargs"]["word_timestamps"] is True
    assert len(out["segments"]) == 1 and out["language"] == "en"
