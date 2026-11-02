"""Lazy faster-whisper transcription adapter for Vietnamese speech."""

from dataclasses import dataclass
import threading
from typing import Any, Callable, Optional

import numpy as np


class SpeechModelError(RuntimeError):
    """Report model initialization or inference failure at one boundary."""


@dataclass(frozen=True)
class TranscriptionResult:
    """Represent normalized text and metadata consumed by the controller."""

    text: str
    language: str
    duration_seconds: float


def _faster_whisper_model(model_size: str, **kwargs):
    """Import the optional GPU dependency only on first transcription."""
    from faster_whisper import WhisperModel

    return WhisperModel(model_size, **kwargs)


class WhisperTranscriber:
    """Load one configured Whisper model lazily and transcribe mono samples."""

    def __init__(self, model_size: str = 'small', device: str = 'cuda',
                 compute_type: str = 'float16', language: str = 'vi',
                 model_factory: Optional[Callable[..., Any]] = None):
        """Retain model settings without importing faster-whisper or CUDA."""
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model_factory = model_factory or _faster_whisper_model
        self._model = None
        self._model_lock = threading.Lock()

    def transcribe(self, samples: np.ndarray,
                   sample_rate: int) -> TranscriptionResult:
        """Return joined segment text while preserving silence as empty text."""
        if sample_rate <= 0:
            raise ValueError('sample_rate must be positive')
        audio = np.ascontiguousarray(np.asarray(samples, dtype=np.float32).reshape(-1))
        model = self._load_model()
        try:
            segments, info = model.transcribe(audio, language=self.language)
            text_parts = []
            for segment in segments:
                text = str(segment.text).strip()
                if text:
                    text_parts.append(text)
        except Exception as error:
            raise SpeechModelError(f'Speech transcription failed: {error}') from error

        detected_language = getattr(info, 'language', None) or self.language
        return TranscriptionResult(
            text=' '.join(text_parts),
            language=str(detected_language),
            duration_seconds=float(audio.size) / sample_rate,
        )

    def _load_model(self):
        """Construct the model exactly once, including under concurrent callers."""
        with self._model_lock:
            if self._model is not None:
                return self._model
            try:
                model = self._model_factory(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            except Exception as error:
                raise SpeechModelError(
                    f'Unable to initialize speech model: {error}') from error
            if model is None:
                raise SpeechModelError('Unable to initialize speech model: empty model')
            self._model = model
            return self._model
