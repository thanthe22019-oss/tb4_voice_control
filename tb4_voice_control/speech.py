"""Lazy Gemini transcription adapter for Vietnamese speech."""

import base64
from dataclasses import dataclass
import io
import math
import os
from typing import Any, Callable
import wave

import numpy as np


class SpeechModelError(RuntimeError):
    """Report model initialization or inference failure at one boundary."""


@dataclass(frozen=True)
class TranscriptionResult:
    """Represent normalized text and metadata consumed by the controller."""

    text: str
    language: str
    duration_seconds: float


def _gemini_client(api_key: str):
    """Import the optional SDK only on first real transcription."""
    from google import genai
    # In the pinned Generate Content transport, unset retry options mean one attempt.
    return genai.Client(api_key=api_key)


def _encode_wav(audio: np.ndarray, sample_rate: int) -> str:
    """Encode clipped mono PCM16 audio entirely in memory."""
    pcm = (np.clip(audio, -1, 1) * 32767).astype('<i2')
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def _api_error_message(error: Exception) -> str:
    """Categorize errors using type/status metadata, never provider text."""
    names = {cls.__name__ for cls in type(error).__mro__}
    status = getattr(error, 'status_code', None)
    if status is None:
        status = getattr(error, 'code', None)
    if status is None:
        status = getattr(getattr(error, 'response', None), 'status_code', None)
    if isinstance(error, TimeoutError) or names & {'TimeoutException', 'APITimeoutError'}:
        return 'Speech transcription timeout; try again.'
    if status in (401, 403):
        return 'Speech authentication failed; check GEMINI_API_KEY.'
    if status == 429:
        return 'Speech rate limit reached; try again later.'
    if isinstance(error, ConnectionError) or names & {'TransportError', 'APIConnectionError'}:
        return 'Speech network connection failed; check connectivity.'
    return 'Speech transcription failed; try again.'


class GeminiTranscriber:
    """Transcribe mono samples using a lazy Generate Content client."""

    def __init__(self, model: str = 'gemini-3.8-flash', language: str = 'vi',
                 request_timeout_seconds: float = 120.0, client: Any | None = None,
                 client_factory: Callable[[str], Any] | None = None):
        if not math.isfinite(request_timeout_seconds) or request_timeout_seconds <= 0:
            raise ValueError('request timeout must be finite and positive')
        self.model = model
        self.language = language
        self.request_timeout_seconds = request_timeout_seconds
        self._client = client
        self._client_factory = client_factory or _gemini_client

    def transcribe(self, samples: np.ndarray,
                   sample_rate: int) -> TranscriptionResult:
        """Return a normalized transcript and input audio metadata."""
        if sample_rate <= 0:
            raise ValueError('sample_rate must be positive')
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        if self._client is None:
            api_key = os.environ.get('GEMINI_API_KEY', '').strip()
            if not api_key:
                raise SpeechModelError('Speech setup requires GEMINI_API_KEY.')
            try:
                self._client = self._client_factory(api_key)
            except Exception:
                raise SpeechModelError(
                    'Speech setup failed; check google-genai installation and configuration.'
                ) from None
        request = {
            'model': self.model,
            'contents': [{'role': 'user', 'parts': [{
                'text': 'Chuyển lời nói tiếng Việt trong audio thành đúng một câu lệnh '
                        'điều hướng. '
                        'Chỉ trả về nguyên văn câu lệnh; nếu không nghe rõ, trả về chuỗi rỗng. '
                        'Không giải thích.',
            }, {
                'inline_data': {'data': _encode_wav(audio, sample_rate),
                                'mime_type': 'audio/wav'},
            }]}],
            # The SDK validates this dict as GenerateContentConfig/HttpOptions.
            # Dict input keeps the injected boundary usable without the optional SDK.
            'config': {
                'store': False,
                'automatic_continuation': False,
                'http_options': {'timeout': self.request_timeout_seconds * 1000},
            },
        }
        try:
            response = self._client.models.generate_content(**request)
        except Exception as error:
            raise SpeechModelError(_api_error_message(error)) from None
        output_text = getattr(response, 'text', None)
        if not isinstance(output_text, str):
            raise SpeechModelError('Speech service returned a malformed transcript.')
        return TranscriptionResult(
            text=output_text.strip(), language=self.language,
            duration_seconds=float(audio.size) / sample_rate,
        )
