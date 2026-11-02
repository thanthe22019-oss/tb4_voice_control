"""faster-whisper boundary tests without CUDA or model downloads."""

from types import SimpleNamespace

import numpy as np
import pytest

from tb4_voice_control.speech import SpeechModelError, WhisperTranscriber


class FakeWhisperModel:
    """Return realistic segment and transcription-info structures."""

    def __init__(self, segments=(), language='vi'):
        """Configure output and retain transcription inputs."""
        self.segments = segments
        self.language = language
        self.calls = []

    def transcribe(self, samples, **kwargs):
        """Capture normalized input and return an iterable plus info."""
        self.calls.append((samples, kwargs))
        segments = (SimpleNamespace(text=text) for text in self.segments)
        return segments, SimpleNamespace(language=self.language)


class FakeModelFactory:
    """Capture model construction and optionally fail initialization."""

    def __init__(self, model=None, error=None):
        """Configure the external model boundary."""
        self.model = model
        self.error = error
        self.calls = []

    def __call__(self, model_size, **kwargs):
        """Construct one fake model with the requested CUDA settings."""
        self.calls.append((model_size, kwargs))
        if self.error is not None:
            raise self.error
        return self.model


def test_model_load_is_lazy_cached_and_uses_cuda_defaults():
    """Construction must not touch CUDA and first use must honor demo settings."""
    model = FakeWhisperModel([' Đi đến ', ' khu vực A. '])
    factory = FakeModelFactory(model)
    transcriber = WhisperTranscriber(model_factory=factory)
    assert factory.calls == []

    result = transcriber.transcribe(np.zeros(16000, dtype=np.float32), 16000)
    transcriber.transcribe(np.zeros(8000, dtype=np.float32), 16000)

    assert factory.calls == [('small', {'device': 'cuda',
                                        'compute_type': 'float16'})]
    assert model.calls[0][1] == {'language': 'vi'}
    assert result.text == 'Đi đến khu vực A.'
    assert result.language == 'vi'
    assert result.duration_seconds == 1.0


def test_audio_is_flattened_to_contiguous_float32_before_transcription():
    """Non-contiguous or column input cannot leak an incompatible model buffer."""
    model = FakeWhisperModel(['A'])
    transcriber = WhisperTranscriber(model_factory=FakeModelFactory(model))
    source = np.arange(8, dtype=np.float64).reshape(4, 2)[:, :1]

    transcriber.transcribe(source, 16000)

    samples, = (model.calls[0][0],)
    assert samples.shape == (4,)
    assert samples.dtype == np.float32
    assert samples.flags.c_contiguous
    np.testing.assert_array_equal(
        samples, np.array([0, 2, 4, 6], dtype=np.float32))


def test_empty_segments_return_an_empty_transcript():
    """Silence must remain a valid empty result for the controller to ignore."""
    model = FakeWhisperModel(['  ', '\n'])
    transcriber = WhisperTranscriber(model_factory=FakeModelFactory(model))

    result = transcriber.transcribe(np.zeros(4000, dtype=np.float32), 16000)

    assert result.text == ''
    assert result.language == 'vi'
    assert result.duration_seconds == 0.25


def test_model_initialization_failure_is_a_typed_speech_error():
    """CUDA/model failures must stop at the speech boundary before routing."""
    factory = FakeModelFactory(error=RuntimeError('CUDA driver unavailable'))
    transcriber = WhisperTranscriber(model_factory=factory)

    with pytest.raises(SpeechModelError, match='CUDA driver unavailable'):
        transcriber.transcribe(np.zeros(10, dtype=np.float32), 16000)

    assert len(factory.calls) == 1


def test_model_transcription_failure_is_a_typed_speech_error():
    """Runtime inference failures must not escape as backend-specific exceptions."""
    class BrokenModel:
        """Emulate an initialized model whose inference fails."""

        def transcribe(self, samples, **kwargs):
            """Raise the external inference error."""
            raise RuntimeError('out of GPU memory')

    transcriber = WhisperTranscriber(
        model_factory=FakeModelFactory(BrokenModel()))

    with pytest.raises(SpeechModelError, match='out of GPU memory'):
        transcriber.transcribe(np.zeros(10, dtype=np.float32), 16000)
