"""Drive the real Qt runtime window offscreen with deterministic adapters."""

import threading

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
import pytest

from tb4_voice_control.regions import GoalPose
from tb4_voice_control.route_executor import LegProgress, RouteState
from tb4_voice_control.runtime_controller import RuntimeController
from tb4_voice_control.speech import TranscriptionResult
from tb4_voice_control.voice_app import VoiceControlWindow

from test_runtime_controller import runtime_map


@pytest.fixture(scope='module')
def app():
    """Provide one offscreen Qt event loop for the module."""
    return QApplication.instance() or QApplication([])


class Recorder:
    """Return deterministic mono audio without opening a device."""

    def __init__(self):
        """Count push-to-talk lifecycle calls."""
        self.starts = 0
        self.stops = 0

    def start(self):
        """Record capture start."""
        self.starts += 1

    def stop(self):
        """Record capture stop and return one short sample buffer."""
        self.stops += 1
        return np.ones(160, dtype=np.float32)


class Transcriber:
    """Return one stable Vietnamese transcript and GPU configuration."""

    device = 'cuda'
    model_size = 'small'
    compute_type = 'float16'

    def transcribe(self, samples, sample_rate):
        """Validate worker arguments and produce a real result object."""
        assert samples.shape == (160,)
        assert sample_rate == 16000
        return TranscriptionResult('Đi đến B', 'vi', 0.01)


class SlowTranscriber(Transcriber):
    """Hold inference until a test explicitly releases external work."""

    def __init__(self):
        """Expose inference entry and release synchronization."""
        self.entered = threading.Event()
        self.release = threading.Event()

    def transcribe(self, samples, sample_rate):
        """Block beyond the UI shutdown timeout before returning."""
        self.entered.set()
        assert self.release.wait(2)
        return super().transcribe(samples, sample_rate)


class Backend:
    """Hold navigation until the UI issues cancellation."""

    def __init__(self):
        """Create route-call evidence and an admission barrier."""
        self.calls = []
        self.entered = threading.Event()

    def execute(self, region, cancel_event, on_progress):
        """Publish progress then cooperatively await cancellation."""
        self.calls.append(region.id)
        self.entered.set()
        on_progress(LegProgress(region.id, distance_remaining=1.5,
                                elapsed_seconds=2.0))
        cancel_event.wait(2)
        return RouteState.CANCELED


class SuccessBackend(Backend):
    """Complete one route without waiting for cancellation."""

    def execute(self, region, cancel_event, on_progress):
        """Publish one final progress update and succeed."""
        self.calls.append(region.id)
        self.entered.set()
        on_progress(LegProgress(region.id, distance_remaining=0.0,
                                elapsed_seconds=1.0))
        return RouteState.SUCCEEDED


def make_window(tmp_path, backend=None, recorder=None, transcriber=None,
                shutdown_timeout_ms=1000):
    """Build one visible window and return all owned test boundaries."""
    semantic, occupancy = runtime_map(tmp_path)
    backend = backend or Backend()
    runtime = RuntimeController(
        semantic, occupancy, backend,
        current_pose=lambda: GoalPose(2.0, 2.0, 0.0),
    )
    recorder = recorder or Recorder()
    transcriber = transcriber or Transcriber()
    shutdown_calls = []
    widget = VoiceControlWindow(
        runtime, recorder, transcriber, sample_rate=16000,
        connection_status='Nav2 sẵn sàng',
        gpu_status='NVIDIA CUDA sẵn sàng',
        shutdown_ros=lambda: shutdown_calls.append(True),
        shutdown_timeout_ms=shutdown_timeout_ms,
    )
    widget.show()
    return widget, backend, recorder, shutdown_calls


@pytest.fixture
def window(app, tmp_path):
    """Create a real runtime window with faked external adapters."""
    widget, backend, recorder, shutdown_calls = make_window(tmp_path)
    app.processEvents()
    yield widget, backend, recorder, shutdown_calls
    widget.close()
    wait_until(app, lambda: not widget.isVisible())


def wait_until(app, predicate, timeout=2000):
    """Pump queued connections until a visible condition becomes true."""
    elapsed = 0
    while elapsed < timeout and not predicate():
        app.processEvents()
        QTest.qWait(10)
        elapsed += 10
    assert predicate()


def test_window_shows_runtime_context_and_push_to_talk_pipeline(window, app):
    """Dropping any runtime signal leaves a required diagnostic field stale."""
    widget, backend, recorder, _ = window
    assert 'Nav2 sẵn sàng' in widget.connection_label.text()
    assert 'NVIDIA CUDA' in widget.gpu_label.text()
    assert 'Khu vực A' in widget.valid_regions_label.text()
    assert 'Phòng thí nghiệm' in widget.valid_regions_label.text()
    assert widget.record_button.text() == 'Giữ để nói'

    QTest.mousePress(widget.record_button, Qt.LeftButton)
    wait_until(app, lambda: recorder.starts == 1)
    QTest.mouseRelease(widget.record_button, Qt.LeftButton)
    wait_until(app, lambda: backend.entered.is_set())
    assert recorder.stops == 1
    assert widget.transcript_view.toPlainText() == 'Đi đến B'
    assert 'GO_TO' in widget.intent_label.text()
    assert 'Phòng thí nghiệm' in widget.route_list.text()
    assert '1/1' in widget.leg_label.text()
    assert '1.50 m' in widget.progress_label.text()
    assert not widget.record_button.isEnabled()
    assert not widget.text_input.isEnabled()
    assert not widget.send_button.isEnabled()
    assert widget.cancel_button.isEnabled()


def test_cancel_and_typed_error_restore_command_controls(window, app):
    """Cancellation must not leave the voice runtime permanently locked."""
    widget, backend, _, _ = window
    widget.text_input.setText('Đi đến B')
    QTest.mouseClick(widget.send_button, Qt.LeftButton)
    wait_until(app, lambda: backend.entered.is_set())
    wait_until(app, lambda: not widget.record_button.isEnabled())
    QTest.mouseClick(widget.cancel_button, Qt.LeftButton)
    wait_until(app, lambda: widget.record_button.isEnabled())
    assert not widget.cancel_button.isEnabled()
    assert 'Đã hủy' in widget.status_label.text()

    widget.text_input.setText('Đi đến nơi không có')
    QTest.mouseClick(widget.send_button, Qt.LeftButton)
    wait_until(app, lambda: 'unknown_region' in widget.error_label.text())
    assert widget.record_button.isEnabled()
    assert 'Khu vực A' in widget.error_label.text()


def test_close_is_bounded_and_shuts_ros_exactly_once(window, app):
    """Repeated close paths cannot destroy the ROS context more than once."""
    widget, _, _, shutdown_calls = window
    assert widget.close()
    app.processEvents()
    widget.shutdown()
    assert shutdown_calls == [True]


def test_success_completion_reenables_command_controls(app, tmp_path):
    """Successful completion must unlock text and push-to-talk controls."""
    widget, backend, _, shutdown_calls = make_window(
        tmp_path, backend=SuccessBackend())
    widget.text_input.setText('Đi đến B')
    QTest.mouseClick(widget.send_button, Qt.LeftButton)
    wait_until(app, lambda: backend.entered.is_set())
    wait_until(app, lambda: 'thành công' in widget.status_label.text())
    assert widget.record_button.isEnabled()
    assert widget.text_input.isEnabled()
    assert widget.send_button.isEnabled()
    assert not widget.cancel_button.isEnabled()
    widget.close()
    wait_until(app, lambda: shutdown_calls == [True])


def test_close_rejects_queued_command_before_navigation_admission(app, tmp_path):
    """A queued text event cannot start a route after shutdown begins."""
    widget, backend, _, shutdown_calls = make_window(tmp_path)
    widget.text_requested.emit('Đi đến B')
    widget.close()
    wait_until(app, lambda: shutdown_calls == [True])
    assert backend.calls == []


def test_close_cancels_active_route_before_destroying_ros(app, tmp_path):
    """ROS lifetime must extend through cooperative route cancellation."""
    widget, backend, _, shutdown_calls = make_window(tmp_path)
    widget.text_input.setText('Đi đến B')
    QTest.mouseClick(widget.send_button, Qt.LeftButton)
    wait_until(app, lambda: backend.entered.is_set())
    widget.close()
    wait_until(app, lambda: shutdown_calls == [True])
    assert backend.calls == ['b']
    assert not widget._navigation_thread.isRunning()


def test_close_stops_active_recording_without_transcription(app, tmp_path):
    """Closing push-to-talk must release the microphone stream immediately."""
    recorder = Recorder()
    transcriber = SlowTranscriber()
    widget, _, _, shutdown_calls = make_window(
        tmp_path, recorder=recorder, transcriber=transcriber)
    QTest.mousePress(widget.record_button, Qt.LeftButton)
    wait_until(app, lambda: recorder.starts == 1)
    widget.close()
    wait_until(app, lambda: shutdown_calls == [True])
    assert recorder.stops == 1
    assert not transcriber.entered.is_set()


def test_long_inference_defers_close_and_ros_shutdown(app, tmp_path):
    """Non-cancelable inference must outlive neither its QThread nor window."""
    transcriber = SlowTranscriber()
    widget, _, recorder, shutdown_calls = make_window(
        tmp_path, transcriber=transcriber, shutdown_timeout_ms=20)
    QTest.mousePress(widget.record_button, Qt.LeftButton)
    wait_until(app, lambda: recorder.starts == 1)
    QTest.mouseRelease(widget.record_button, Qt.LeftButton)
    wait_until(app, lambda: transcriber.entered.is_set())
    assert not widget.close()
    assert shutdown_calls == []
    assert widget._speech_thread.isRunning()
    assert widget.isVisible()
    transcriber.release.set()
    wait_until(app, lambda: shutdown_calls == [True])
    assert not widget._speech_thread.isRunning()
    assert not widget.isVisible()
