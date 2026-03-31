"""Local voice transcription using faster-whisper."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration_seconds: float


class Transcriber:
    """Lazy-loading wrapper around faster_whisper.WhisperModel."""

    def __init__(self, model_size: str = "small") -> None:
        self._model_size = model_size
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",
            )

    def transcribe(self, file_path: str, language: str = "uk") -> TranscriptionResult:
        self._load()
        segments, info = self._model.transcribe(
            file_path,
            language=language,
            vad_filter=True,
            beam_size=5,
        )
        text = " ".join(seg.text.strip() for seg in segments)
        return TranscriptionResult(
            text=text,
            language=info.language,
            duration_seconds=info.duration,
        )
