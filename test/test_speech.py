"""Gemini speech boundary tests without credentials or network requests."""

import base64
import io
import sys
from types import SimpleNamespace
import wave

import numpy as np
import pytest

from tb4_voice_control import speech


class FakeModelsClient:
    """Capture requests at the external Generate Content boundary."""

    def __init__(self, output_text=' Đi đến khu vực A. ', error=None, response=None):
        self.models = self
        self.output_text = output_text
        self.error = error
        self.response = response
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({'model': model, 'contents': contents, 'config': config})
        if self.error is not None:
            raise self.error
        if self.response is not None:
            return self.response
        return SimpleNamespace(text=self.output_text)


def test_request_contains_clipped_mono_pcm16_wav():
    client = FakeModelsClient()
    source = np.array([[-2., -.5], [0., .5], [1., 2.]])
    speech.GeminiTranscriber(client=client).transcribe(source, 8000)

    text_part, audio_part = client.calls[0]['contents'][0]['parts']
    assert text_part == {
        'text': 'Chuyển lời nói tiếng Việt trong audio thành đúng một câu lệnh điều hướng. '
                'Chỉ trả về nguyên văn câu lệnh; nếu không nghe rõ, trả về chuỗi rỗng. '
                'Không giải thích.',
    }
    assert set(audio_part) == {'inline_data'}
    audio_part = audio_part['inline_data']
    assert audio_part['mime_type'] == 'audio/wav'
    with wave.open(io.BytesIO(base64.b64decode(audio_part['data']))) as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 8000
        assert wav.getnframes() == 6
        pcm = np.frombuffer(wav.readframes(6), dtype='<i2')
    np.testing.assert_array_equal(pcm, [-32767, -16383, 0, 16383, 32767, 32767])


def test_request_is_stateless_bounded_and_has_no_continuation():
    client = FakeModelsClient()
    speech.GeminiTranscriber(client=client).transcribe([0.], 16000)

    request = client.calls[0]
    assert set(request) == {'model', 'contents', 'config'}
    assert request['model'] == 'gemini-3.5-transcribe'
    assert request['config'] == {
        'store': False, 'automatic_continuation': False,
        'http_options': {'timeout': 120000},
    }


def test_valid_output_returns_existing_result_contract():
    client = FakeModelsClient()
    result = speech.GeminiTranscriber(client=client).transcribe(np.zeros(4000), 16000)

    assert result == speech.TranscriptionResult('Đi đến khu vực A.', 'vi', .25)


def test_audio_transcription_parts_return_existing_result_contract():
    response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[
        SimpleNamespace(audio_transcription=SimpleNamespace(text=' Đi đến khu vực A. ')),
    ]))], text='Fallback must not override the transcription')
    result = speech.GeminiTranscriber(client=FakeModelsClient(response=response)).transcribe(
        np.zeros(4000), 16000)

    assert result == speech.TranscriptionResult('Đi đến khu vực A.', 'vi', .25)


def test_audio_transcription_parts_preserve_order():
    response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[
        SimpleNamespace(audio_transcription=SimpleNamespace(text=' Đi đến ')),
        SimpleNamespace(text='Unrelated text part'),
        SimpleNamespace(audio_transcription=SimpleNamespace(text=' \n ')),
        SimpleNamespace(audio_transcription=SimpleNamespace(text=42)),
        SimpleNamespace(audio_transcription=SimpleNamespace(text=' khu vực A. ')),
    ])), SimpleNamespace(content=SimpleNamespace(parts=[
        SimpleNamespace(audio_transcription=SimpleNamespace(text='Ignore another candidate')),
    ]))])
    result = speech.GeminiTranscriber(client=FakeModelsClient(response=response)).transcribe(
        [0.], 16000)

    assert result.text == 'Đi đến khu vực A.'


@pytest.mark.parametrize('text', ['', ' \n '])
def test_empty_audio_transcription_is_valid(text):
    response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[
        SimpleNamespace(audio_transcription=SimpleNamespace(text=text)),
    ]))], text='Fallback must not override an empty transcription')
    result = speech.GeminiTranscriber(client=FakeModelsClient(response=response)).transcribe(
        [0.], 16000)

    assert result == speech.TranscriptionResult('', 'vi', 1 / 16000)


@pytest.mark.parametrize('sample_rate', [0, -1])
def test_sample_rate_must_be_positive(sample_rate):
    with pytest.raises(ValueError, match='sample_rate'):
        speech.GeminiTranscriber(client=FakeModelsClient()).transcribe([], sample_rate)


@pytest.mark.parametrize('timeout', [0, -1, float('nan'), float('inf')])
def test_timeout_must_be_positive(timeout):
    with pytest.raises(ValueError, match='timeout'):
        speech.GeminiTranscriber(request_timeout_seconds=timeout)


def test_missing_api_key_is_actionable_and_does_not_construct_client(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', ' \n ')
    calls = []
    transcriber = speech.GeminiTranscriber(client_factory=lambda key: calls.append(key))
    assert calls == []

    with pytest.raises(speech.SpeechModelError, match='GEMINI_API_KEY'):
        transcriber.transcribe([0.], 16000)
    assert calls == []


def test_client_is_lazy_cached_and_reads_trimmed_key_at_first_use(monkeypatch):
    calls = []
    client = FakeModelsClient()

    def factory(key):
        calls.append(key)
        return client

    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    transcriber = speech.GeminiTranscriber(client_factory=factory)
    assert calls == []
    monkeypatch.setenv('GEMINI_API_KEY', ' test-key ')
    transcriber.transcribe([0.], 16000)
    transcriber.transcribe([0.], 16000)
    assert calls == ['test-key']


def test_default_factory_disables_sdk_retries_and_imports_lazily(monkeypatch):
    calls = []
    client = FakeModelsClient()
    fake_genai = SimpleNamespace(
        Client=lambda **kw: calls.append(kw) or client)
    monkeypatch.setitem(sys.modules, 'google', SimpleNamespace(genai=fake_genai))
    monkeypatch.setitem(sys.modules, 'google.genai', fake_genai)
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    transcriber = speech.GeminiTranscriber()
    assert calls == []
    transcriber.transcribe([0.], 16000)
    assert calls == [{'api_key': 'test-key'}]


def test_empty_output_is_a_valid_transcript(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    result = speech.GeminiTranscriber(
        client=FakeModelsClient(' \n ')).transcribe([0.], 16000)
    assert result == speech.TranscriptionResult('', 'vi', 1 / 16000)


@pytest.mark.parametrize('response', [SimpleNamespace(), SimpleNamespace(text=None),
                                      SimpleNamespace(text=42),
                                      SimpleNamespace(candidates=[SimpleNamespace(
                                          content=SimpleNamespace(parts=[SimpleNamespace(
                                              audio_transcription=SimpleNamespace(text=42))]))])])
def test_malformed_output_is_a_typed_error(response):
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw: response))
    with pytest.raises(speech.SpeechModelError, match='malformed'):
        speech.GeminiTranscriber(client=client).transcribe([0.], 16000)


class HttpFailure(Exception):

    def __init__(self, status_code):
        super().__init__('SECRET_SENTINEL synthetic-offline-test-key')
        self.status_code = status_code


class APIConnectionError(Exception):
    """Match SDK wrapper type metadata without requiring the optional SDK."""


class APITimeoutError(APIConnectionError):
    """Timeout must take priority over the network parent class."""


@pytest.mark.parametrize(('error', 'category'), [
    (APIConnectionError('SECRET_SENTINEL'), 'network'),
    (APITimeoutError('SECRET_SENTINEL'), 'timeout'),
])
def test_sdk_wrapper_metadata_is_actionable(error, category):
    assert category in speech._api_error_message(error)


@pytest.mark.parametrize(('error', 'category'), [
    (TimeoutError('SECRET_SENTINEL'), 'timeout'),
    (HttpFailure(504), 'timeout'),
    (HttpFailure(401), 'authentication'),
    (HttpFailure(403), 'authentication'),
    (HttpFailure(429), 'rate limit'),
    (ConnectionError('SECRET_SENTINEL'), 'network'),
    (APIConnectionError('SECRET_SENTINEL'), 'network'),
    (APITimeoutError('SECRET_SENTINEL'), 'timeout'),
    (RuntimeError('SECRET_SENTINEL'), 'failed'),
])
def test_api_failures_are_categorized_without_leaking_details(error, category):
    client = FakeModelsClient(error=error)
    with pytest.raises(speech.SpeechModelError, match=category) as caught:
        speech.GeminiTranscriber(client=client).transcribe([0.], 16000)
    assert 'SECRET_SENTINEL' not in str(caught.value)
    assert 'synthetic-offline-test-key' not in str(caught.value)
    assert caught.value.__suppress_context__


def test_client_setup_failure_is_sanitized(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'SECRET_SENTINEL')

    def broken_factory(key):
        raise RuntimeError(key)

    with pytest.raises(speech.SpeechModelError, match='setup') as caught:
        speech.GeminiTranscriber(client_factory=broken_factory).transcribe([0.], 16000)
    assert 'SECRET_SENTINEL' not in str(caught.value)
