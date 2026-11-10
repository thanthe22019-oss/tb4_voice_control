"""Offline acceptance of the production adapter against the optional real SDK."""

import base64
from importlib import import_module
from importlib.metadata import version
import io
import json
import time
import wave

import numpy as np
import pytest

from tb4_voice_control import speech


@pytest.fixture(scope='module', autouse=True)
def httpx(request):
    """Require the bounded optional SDK only for explicit offline acceptance."""
    if not request.config.getoption('--run-speech-sdk'):
        pytest.skip('run with .venv-speech/bin/python -m pytest --run-speech-sdk')
    assert version('google-genai').startswith('2.33.'), 'install requirements-speech.txt'
    import_module('google.genai')
    return import_module('httpx')


@pytest.fixture
def sdk_transport(monkeypatch, httpx):
    """Replace HTTP only: exercise lazy production client construction too."""
    monkeypatch.setenv('GEMINI_API_KEY', 'synthetic-offline-test-key')
    monkeypatch.delenv('GOOGLE_GENAI_USE_VERTEXAI', raising=False)
    requests = []
    handlers = []

    def handle(request):
        requests.append(request)
        assert len(requests) == 1, 'unexpected retry or continuation request'
        return handlers[0](request)

    original_init = httpx.Client.__init__

    def init(client, *args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(handle)
        return original_init(client, *args, **kwargs)

    def forbidden_sleep(seconds):
        pytest.fail(f'SDK attempted retry sleep: {seconds}')

    monkeypatch.setattr(httpx.Client, '__init__', init)
    monkeypatch.setattr(time, 'sleep', forbidden_sleep)
    return requests, handlers


@pytest.mark.parametrize('finish_reason', ['STOP', 'CONTINUATION'])
def test_real_sdk_accepts_inline_wav_and_stateless_config(sdk_transport, finish_reason, httpx):
    requests, handlers = sdk_transport
    handlers.append(lambda request: httpx.Response(200, json={
        'candidates': [{'content': {'role': 'model', 'parts': [
            {'text': ' Đi đến khu vực A. '}]}, 'finishReason': finish_reason,
            'continuationToken': 'bW9jay1jb250aW51YXRpb24='}],
    }))
    transcriber = speech.GeminiTranscriber(request_timeout_seconds=1.25)
    try:
        result = transcriber.transcribe([-2., 0., 2.], 8000)
    finally:
        if transcriber._client is not None:
            transcriber._client.close()

    assert result == speech.TranscriptionResult('Đi đến khu vực A.', 'vi', 3 / 8000)
    assert len(requests) == 1
    request = requests[0]
    assert request.method == 'POST'
    assert request.url.path.endswith('/models/gemini-3.5-transcribe:generateContent')
    assert set(request.extensions['timeout'].values()) == {1.25}
    body = json.loads(request.content)
    assert body['store'] is False
    text_part, audio_part = body['contents'][0]['parts']
    assert 'Không giải thích.' in text_part['text']
    assert audio_part['inlineData']['mime_type'] == 'audio/wav'
    with wave.open(io.BytesIO(base64.urlsafe_b64decode(audio_part['inlineData']['data']))) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 8000)
        np.testing.assert_array_equal(
            np.frombuffer(wav.readframes(3), dtype='<i2'), [-32767, 0, 32767])


def test_real_sdk_decodes_audio_transcription_part(sdk_transport, httpx):
    requests, handlers = sdk_transport
    handlers.append(lambda request: httpx.Response(200, json={
        'candidates': [{'content': {'role': 'model', 'parts': [
            {'audioTranscription': {'text': ' Đi đến khu vực A. '}}]},
            'finishReason': 'STOP'}],
    }))
    transcriber = speech.GeminiTranscriber()
    try:
        result = transcriber.transcribe(np.zeros(4000), 16000)
    finally:
        if transcriber._client is not None:
            transcriber._client.close()

    assert result == speech.TranscriptionResult('Đi đến khu vực A.', 'vi', .25)
    assert len(requests) == 1


@pytest.mark.parametrize(('failure', 'category'), [
    (429, 'rate limit'), (500, 'failed'), (503, 'failed'),
    ('connection', 'network'), ('timeout', 'timeout'),
])
def test_real_sdk_failure_has_one_attempt_and_no_retry_wait(
        sdk_transport, failure, category, httpx):
    requests, handlers = sdk_transport

    def fail(request):
        if failure == 'connection':
            raise httpx.ConnectError('SECRET_SENTINEL', request=request)
        if failure == 'timeout':
            raise httpx.ReadTimeout('SECRET_SENTINEL', request=request)
        return httpx.Response(failure, headers={'Retry-After': '3600'}, json={
            'error': {'code': failure, 'message': 'SECRET_SENTINEL', 'status': 'ERROR'},
        })

    handlers.append(fail)
    transcriber = speech.GeminiTranscriber(request_timeout_seconds=1.25)
    try:
        with pytest.raises(speech.SpeechModelError, match=category) as caught:
            transcriber.transcribe([0.], 16000)
    finally:
        if transcriber._client is not None:
            transcriber._client.close()
    assert len(requests) == 1
    assert caught.value.__suppress_context__
    assert 'SECRET_SENTINEL' not in str(caught.value)
    assert 'synthetic-offline-test-key' not in str(caught.value)


@pytest.mark.parametrize(('wrapper', 'category'), [
    ('APIConnectionError', 'network'), ('APITimeoutError', 'timeout'),
])
def test_actual_sdk_wrapper_errors_remain_actionable_and_sanitized(wrapper, category, httpx):
    from google.genai._gaos.lib import compat_errors
    from types import SimpleNamespace

    request = httpx.Request('POST', 'https://offline.invalid')
    error = getattr(compat_errors, wrapper)(request=request)

    def fail(**kwargs):
        raise error

    client = SimpleNamespace(models=SimpleNamespace(generate_content=fail))
    with pytest.raises(speech.SpeechModelError, match=category) as caught:
        speech.GeminiTranscriber(client=client).transcribe([0.], 16000)
    assert caught.value.__suppress_context__
    assert 'offline.invalid' not in str(caught.value)
