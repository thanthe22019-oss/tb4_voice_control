"""Push-to-talk audio capture without requiring a physical microphone."""

import numpy as np
import pytest

from tb4_voice_control.audio_capture import (
    AudioDeviceError,
    AudioRecorder,
    RecordingStateError,
)


class FakeInputStream:
    """Expose the sounddevice stream lifecycle and callback boundary."""

    def __init__(self, **kwargs):
        """Remember the requested input format."""
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self):
        """Mark the fake stream active."""
        self.started = True

    def stop(self):
        """Mark the fake stream stopped."""
        self.stopped = True

    def close(self):
        """Mark the fake stream closed."""
        self.closed = True

    def feed(self, values):
        """Deliver one complete mono block through the real recorder callback."""
        block = np.asarray(values, dtype=np.float32).reshape(-1, 1)
        self.kwargs['callback'](block, len(block), None, None)


class FakeSoundDevice:
    """Create controllable input streams or emulate an unavailable device."""

    def __init__(self, error=None):
        """Configure the next stream open and retain created streams."""
        self.error = error
        self.streams = []

    def InputStream(self, **kwargs):
        """Return a fake stream with sounddevice-compatible construction."""
        if self.error is not None:
            raise self.error
        stream = FakeInputStream(**kwargs)
        self.streams.append(stream)
        return stream


def test_start_stop_records_16khz_mono_float32_samples():
    """Changing channel count, rate, dtype, or block order corrupts speech input."""
    sounddevice = FakeSoundDevice()
    recorder = AudioRecorder(sounddevice_module=sounddevice)

    recorder.start()
    stream, = sounddevice.streams
    assert stream.kwargs['samplerate'] == 16000
    assert stream.kwargs['channels'] == 1
    assert stream.kwargs['dtype'] == 'float32'
    assert stream.started
    stream.feed([0.25, -0.5])
    stream.feed([0.75])

    samples = recorder.stop()

    assert samples.dtype == np.float32
    np.testing.assert_array_equal(
        samples, np.array([0.25, -0.5, 0.75], dtype=np.float32))
    assert stream.stopped and stream.closed


def test_stop_before_start_has_a_typed_state_error():
    """A stray button-release event must not masquerade as an empty recording."""
    recorder = AudioRecorder(sounddevice_module=FakeSoundDevice())

    with pytest.raises(RecordingStateError, match='not recording'):
        recorder.stop()


def test_second_start_is_rejected_without_opening_another_stream():
    """Repeated press events cannot replace the active stream or lose audio."""
    sounddevice = FakeSoundDevice()
    recorder = AudioRecorder(sounddevice_module=sounddevice)
    recorder.start()

    with pytest.raises(RecordingStateError, match='already recording'):
        recorder.start()

    assert len(sounddevice.streams) == 1
    recorder.stop()


def test_recording_is_truncated_at_the_configured_maximum_duration():
    """An unreleased push-to-talk button cannot grow memory beyond its limit."""
    sounddevice = FakeSoundDevice()
    recorder = AudioRecorder(sample_rate=4, max_record_seconds=1,
                             sounddevice_module=sounddevice)
    recorder.start()
    stream, = sounddevice.streams
    stream.feed([1, 2, 3])
    stream.feed([4, 5, 6])
    stream.feed([7, 8])

    samples = recorder.stop()

    np.testing.assert_array_equal(
        samples, np.array([1, 2, 3, 4], dtype=np.float32))


def test_device_open_failure_is_typed_and_recorder_can_retry():
    """Unavailable input hardware must remain distinguishable from state misuse."""
    sounddevice = FakeSoundDevice(RuntimeError('no default input device'))
    recorder = AudioRecorder(sounddevice_module=sounddevice)

    with pytest.raises(AudioDeviceError, match='no default input device'):
        recorder.start()

    sounddevice.error = None
    recorder.start()
    assert recorder.stop().size == 0
