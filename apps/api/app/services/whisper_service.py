"""Whisper adapter (S5): faster-whisper with word timings preserved.

The model loads lazily on first transcribe. Word-level timestamps are always
requested — captions (S9) and clip boundaries (S6) depend on them.
"""

import structlog
from pathlib import Path

log = structlog.get_logger()


class TranscriptionError(RuntimeError):
    pass


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
            segments, info = self.model.transcribe(
                str(target), language=language,
                word_timestamps=word_timestamps,
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
