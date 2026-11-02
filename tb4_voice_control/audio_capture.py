"""Thread-safe push-to-talk capture at the speech model input boundary."""

import threading
from typing import Any, Optional

import numpy as np


class AudioCaptureError(RuntimeError):
    """Base class for microphone capture failures."""


class AudioDeviceError(AudioCaptureError):
    """Report that the configured input device could not be used."""


class RecordingStateError(AudioCaptureError):
    """Report an invalid push-to-talk lifecycle transition."""


class AudioRecorder:
    """Collect bounded mono float32 blocks from a sounddevice input stream."""

    def __init__(self, sample_rate: int = 16000, max_record_seconds: float = 15,
                 sounddevice_module: Optional[Any] = None):
        """Configure capture without opening or importing an audio device."""
        if sample_rate <= 0:
            raise ValueError('sample_rate must be positive')
        if max_record_seconds <= 0:
            raise ValueError('max_record_seconds must be positive')
        self.sample_rate = int(sample_rate)
        self.max_record_seconds = float(max_record_seconds)
        self._maximum_samples = int(self.sample_rate * self.max_record_seconds)
        self._sounddevice = sounddevice_module
        self._lock = threading.Lock()
        self._state = 'idle'
        self._stream = None
        self._chunks = []
        self._captured_samples = 0

    @property
    def is_recording(self) -> bool:
        """Return whether a push-to-talk capture is currently active."""
        with self._lock:
            return self._state == 'recording'

    def start(self) -> None:
        """Open and start the configured input stream."""
        with self._lock:
            if self._state != 'idle':
                raise RecordingStateError('already recording')
            self._state = 'starting'
            self._chunks = []
            self._captured_samples = 0

        stream = None
        try:
            sounddevice = self._sounddevice or self._import_sounddevice()
            stream = sounddevice.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                callback=self._audio_callback,
            )
            with self._lock:
                self._stream = stream
            stream.start()
        except Exception as error:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            with self._lock:
                self._stream = None
                self._state = 'idle'
                self._chunks = []
                self._captured_samples = 0
            if isinstance(error, AudioDeviceError):
                raise
            raise AudioDeviceError(f'Unable to open input device: {error}') from error

        with self._lock:
            self._state = 'recording'

    def stop(self) -> np.ndarray:
        """Stop capture and return one contiguous mono float32 array."""
        with self._lock:
            if self._state != 'recording':
                raise RecordingStateError('not recording')
            self._state = 'stopping'
            stream = self._stream

        device_error = None
        try:
            stream.stop()
        except Exception as error:
            device_error = error
        try:
            stream.close()
        except Exception as error:
            device_error = device_error or error

        with self._lock:
            if self._chunks:
                samples = np.concatenate(self._chunks).astype(
                    np.float32, copy=False)
            else:
                samples = np.empty(0, dtype=np.float32)
            self._stream = None
            self._state = 'idle'
            self._chunks = []
            self._captured_samples = 0

        if device_error is not None:
            raise AudioDeviceError(
                f'Unable to close input device: {device_error}') from device_error
        return np.ascontiguousarray(samples)

    @staticmethod
    def _import_sounddevice():
        """Import optional PortAudio bindings only when capture begins."""
        try:
            import sounddevice
        except ImportError as error:
            raise AudioDeviceError(
                'sounddevice is not installed; run scripts/setup_speech_venv.sh'
            ) from error
        return sounddevice

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        """Copy the reusable PortAudio block while respecting the memory cap."""
        del frames, time_info, status
        block = np.asarray(indata, dtype=np.float32).reshape(-1).copy()
        with self._lock:
            if self._state not in ('starting', 'recording'):
                return
            remaining = self._maximum_samples - self._captured_samples
            if remaining <= 0:
                return
            if block.size > remaining:
                block = block[:remaining]
            if block.size:
                self._chunks.append(block)
                self._captured_samples += block.size
