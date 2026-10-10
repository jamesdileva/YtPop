"""Whisper adapter (S5): faster-whisper with word timings preserved.

The model loads lazily on first transcribe. Word-level timestamps are always
requested — captions (S9) and clip boundaries (S6) depend on them.

Audio is decoded from a 16kHz mono PCM wav with the stdlib instead of
faster-whisper's `av`-based decoder (see `load_audio`). `av` is imported by
that package at module load even though we never use its decoder, so when
the dependency is absent (trimmed packaged build) a shim stands in and
raises loudly only if the unused path is ever taken.
"""

import sys
import structlog
import types
from pathlib import Path

log = structlog.get_logger()


class TranscriptionError(RuntimeError):
    pass


def _ensure_av_shim() -> None:
    """Guarantee `import av` succeeds when PyAV is not shipped.

    faster_whisper.audio imports `av` at module import time but only uses it
    inside decode_audio(); this service passes decoded numpy audio instead,
    so the real bindings are unnecessary. In the trimmed freeze we exclude
    them (~60MB) and any accidental use of that path fails clearly here.
    """
    if sys.modules.get("av") is not None:
        return
    try:
        import av  # noqa: F401  (real PyAV present)

        return
    except ImportError:
        pass
    stub = types.ModuleType("av")

    def _unavailable(name: str):
        raise TranscriptionError(
            "PyAV is not installed and faster-whisper's file decoder was "
            "reached; audio should be decoded locally instead"
        )

    stub.__getattr__ = _unavailable  # type: ignore[method-assign]
    sys.modules["av"] = stub
    log.warning("av_shim_installed", reason="PyAV not installed")


def load_audio(path: Path):
    """Decode a 16-bit PCM wav into a 16kHz-mono float32 ndarray.

    Uses the stdlib instead of faster-whisper's `av`-based decoder: the
    ingestion step already writes a 16k mono WAV, so this avoids a second
    decode and lets the packaged freeze skip the `av` FFmpeg bindings.
    """
    import wave

    import numpy as np

    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            rate = handle.getframerate()
            frames = handle.getnframes()
            raw = handle.readframes(frames)
    except (wave.Error, EOFError) as e:
        raise TranscriptionError(
            f"could not read wav {path}: {e}") from e
    if width != 2:
        raise TranscriptionError(
            f"expected 16-bit PCM wav, got {width * 8}-bit: {path}")
    if rate != 16000:
        raise TranscriptionError(
            f"expected 16kHz wav, got {rate}Hz: {path}")
    data = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    if data.size == 0:
        raise TranscriptionError(f"wav has no samples: {path}")
    return data


class WhisperService:
    def __init__(
        self, model_name: str = "base", device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model = None

    @property
    def model(self):
        if self._model is None:
            _ensure_av_shim()
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise TranscriptionError(
                    "faster-whisper is not installed"
                ) from e
            log.info(
                "whisper_load", model=self.model_name, device=self.device,
                compute_type=self.compute_type,
            )
            self._model = WhisperModel(
                self.model_name, device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe(
        self, wav_path: str | Path, language: str | None = None,
        word_timestamps: bool = True,
    ) -> dict:
        target = Path(wav_path)
        if not target.is_file():
            raise TranscriptionError(f"audio file not found: {target}")
        try:
            audio = load_audio(target)
            segments, info = self.model.transcribe(
                audio, language=language, word_timestamps=word_timestamps,
            )
            out = []
            for seg in segments:
                words = [
                    {
                        "start": round(float(w.start), 3),
                        "end": round(float(w.end), 3),
                        "word": w.word,
                        "probability": round(float(w.probability), 4),
                    }
                    for w in (seg.words or [])
                ]
                out.append({
                    "start": round(float(seg.start), 3),
                    "end": round(float(seg.end), 3),
                    "text": seg.text.strip(),
                    "confidence": round(float(seg.avg_logprob), 4),
                    "words": words,
                })
        except TranscriptionError:
            raise
        except Exception as e:
            raise TranscriptionError(f"transcription failed: {e}") from e
        detected = getattr(info, "language", None) or (language or "en")
        log.info(
            "whisper_done", path=str(target), language=detected,
            segments=len(out),
        )
        return {
            "language": detected,
            "segments": out,
            "text": " ".join(s["text"] for s in out).strip(),
        }
