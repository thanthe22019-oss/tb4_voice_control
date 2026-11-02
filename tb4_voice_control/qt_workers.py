"""Qt queued-signal bridges for speech and the pure runtime controller."""

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject

from tb4_voice_control.audio_capture import AudioCaptureError
from tb4_voice_control.speech import SpeechModelError


class SpeechWorker(QObject):
    """Own microphone and transcription operations on one dedicated QThread."""

    transcript = pyqtSignal(str)
    error = pyqtSignal(str, str)
    recording_changed = pyqtSignal(bool)

    def __init__(self, recorder, transcriber, sample_rate: int):
        """Retain adapters without touching audio or loading a model."""
        super().__init__()
        self._recorder = recorder
        self._transcriber = transcriber
        self._sample_rate = sample_rate
        self._recording = False

    @pyqtSlot()
    def start_recording(self):
        """Start push-to-talk capture and publish typed device failures."""
        if self._recording:
            return
        try:
            self._recorder.start()
        except Exception as error:  # noqa: B902 - device adapter boundary
            self.error.emit('microphone_error', str(error))
            return
        self._recording = True
        self.recording_changed.emit(True)

    @pyqtSlot()
    def stop_and_transcribe(self):
        """Stop capture, run inference, then emit only the resulting text."""
        if not self._recording:
            return
        try:
            samples = self._recorder.stop()
            self._recording = False
            self.recording_changed.emit(False)
            result = self._transcriber.transcribe(samples, self._sample_rate)
        except AudioCaptureError as error:
            self._recording = False
            self.recording_changed.emit(False)
            self.error.emit('microphone_error', str(error))
            return
        except SpeechModelError as error:
            self.error.emit('model_error', str(error))
            return
        except Exception as error:  # noqa: B902 - injected speech boundary
            self.error.emit('speech_error', str(error))
            return
        self.transcript.emit(result.text)


class NavigationWorker(QObject):
    """Run command admission off UI and bridge callbacks as signals."""

    transcript = pyqtSignal(str)
    command = pyqtSignal(object)
    route = pyqtSignal(object)
    state = pyqtSignal(object)
    progress = pyqtSignal(object)
    error = pyqtSignal(object)

    def __init__(self, controller):
        """Subscribe to every controller event without widget access."""
        super().__init__()
        self._controller = controller
        self._unsubscribe = [
            controller.add_listener('transcript', self.transcript.emit),
            controller.add_listener('command', self.command.emit),
            controller.add_listener('route', self.route.emit),
            controller.add_listener('state', self.state.emit),
            controller.add_listener('progress', self.progress.emit),
            controller.add_listener('error', self.error.emit),
        ]

    @pyqtSlot(str)
    def process_text(self, text):
        """Send typed and transcribed text through the same controller API."""
        self._controller.process_text(text)

    @pyqtSlot()
    def cancel(self):
        """Request cooperative cancellation without waiting or calling Nav2."""
        self._controller.cancel()

    @pyqtSlot(str, str)
    def report_error(self, code, message):
        """Route adapter errors through the controller's typed channel."""
        self._controller.report_error(code, message)

    def detach(self):
        """Disconnect controller callbacks during bounded window shutdown."""
        callbacks, self._unsubscribe = self._unsubscribe, []
        for unsubscribe in callbacks:
            unsubscribe()
