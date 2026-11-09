"""Drive the real Qt runtime window offscreen with deterministic adapters."""

from dataclasses import replace
import threading
from types import SimpleNamespace

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QLabel, QMessageBox
import pytest

from tb4_voice_control.regions import GoalPose
from tb4_voice_control.route_executor import CleanupState, LegProgress, RouteState
from tb4_voice_control.runtime_controller import RuntimeController
from tb4_voice_control.speech import SpeechModelError, TranscriptionResult
from tb4_voice_control.voice_app import VoiceControlWindow

from test_runtime_controller import CleanupBackend, runtime_map
import yaml


@pytest.mark.parametrize('defect,code', [
    ('outside', 'goal_out_of_bounds'), ('occupied', 'goal_not_free'),
    ('invalid', 'invalid_polygon'), ('overlap', 'overlapping_regions'),
])
def test_startup_rejects_invalid_map_before_backend(tmp_path, defect, code, monkeypatch):
    """Geometric configuration errors block backend construction."""
    from types import SimpleNamespace

    import rclpy
    from tb4_voice_control import voice_app

    semantic, occupancy = runtime_map(tmp_path)
    a, b = semantic.regions
    if defect == 'outside':
        a = replace(a, goal=GoalPose(1000.0, 1000.0, 0.0))
    elif defect == 'occupied':
        occupancy.free_mask[8, 2] = False
    elif defect == 'invalid':
        a = replace(a, polygon_pixels=((0, 5), (4, 9), (4, 5), (0, 9)))
    else:
        b = replace(b, polygon_pixels=a.polygon_pixels)
    semantic = replace(semantic, regions=(a, b))
    calls = []
    monkeypatch.setattr(voice_app, '_parse_runtime_arguments',
                        lambda argv: (SimpleNamespace(regions='regions'), []))
    monkeypatch.setattr(voice_app, 'load_regions', lambda path: semantic)
    monkeypatch.setattr(voice_app, 'load_occupancy_map', lambda path: occupancy)
    monkeypatch.setattr(rclpy, 'init', lambda **kwargs: calls.append('ROS initialized'))
    with pytest.raises(ValueError, match=code):
        voice_app.main([])
    assert calls == []


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
    """Return one stable Vietnamese transcript and Gemini configuration."""

    model = 'gemini-3.8-flash'

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
        speech_status=f'Gemini API — {transcriber.model}',
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
    assert widget.speech_label.text() == 'Gemini API — gemini-3.8-flash'
    labels = [label.text() for label in widget.findChildren(QLabel)]
    assert 'Nhận dạng:' in labels
    assert not any('CUDA' in text or 'GPU' in text for text in labels)
    assert 'Khu vực A' in widget.valid_regions_label.text()
    assert 'Phòng thí nghiệm' in widget.valid_regions_label.text()
    assert widget.record_button.text() == 'Giữ để nói'

    QTest.mousePress(widget.record_button, Qt.LeftButton)
    wait_until(app, lambda: recorder.starts == 1)
    QTest.mouseRelease(widget.record_button, Qt.LeftButton)
    wait_until(app, lambda: backend.entered.is_set())
    wait_until(app, lambda: widget.transcript_view.toPlainText() == 'Đi đến B')
    assert recorder.stops == 1
    assert 'GO_TO' in widget.intent_label.text()
    assert 'Phòng thí nghiệm' in widget.route_list.text()
    assert '1/1' in widget.leg_label.text()
    assert '1.50 m' in widget.progress_label.text()
    assert not widget.record_button.isEnabled()
    assert not widget.text_input.isEnabled()
    assert not widget.send_button.isEnabled()
    assert widget.cancel_button.isEnabled()


def test_main_configures_gemini_and_audio_from_yaml(tmp_path, monkeypatch):
    """Runtime settings must reach the speech and audio adapter boundaries."""
    import rclpy
    from tb4_voice_control import nav2_backend, voice_app

    semantic, occupancy = runtime_map(tmp_path)
    config_path = tmp_path / 'voice.yaml'
    config_path.write_text(yaml.safe_dump({
        'provider': 'gemini', 'model': 'configured-gemini-model',
        'language': 'en', 'request_timeout_seconds': 12,
        'sample_rate': 22050, 'max_record_seconds': 7,
    }))
    monkeypatch.setattr(voice_app, '_parse_runtime_arguments', lambda argv: (
        SimpleNamespace(regions='regions', voice_config=config_path), []))
    monkeypatch.setattr(voice_app, 'load_regions', lambda path: semantic)
    monkeypatch.setattr(voice_app, 'load_occupancy_map', lambda path: occupancy)
    monkeypatch.setattr(rclpy, 'init', lambda **kwargs: None)
    monkeypatch.setattr(nav2_backend, 'BasicNavigatorBackend', lambda **kwargs: Backend())
    captured = {}

    def recorder(**kwargs):
        captured['audio'] = kwargs
        return SimpleNamespace(sample_rate=kwargs['sample_rate'])

    def transcriber(**kwargs):
        captured['speech'] = kwargs
        return SimpleNamespace(model='resolved-gemini-model')

    def window(*args, **kwargs):
        captured['window'] = kwargs
        return SimpleNamespace(show=lambda: None, shutdown=lambda: None)

    monkeypatch.setattr(voice_app, 'AudioRecorder', recorder)
    monkeypatch.setattr(voice_app, 'GeminiTranscriber', transcriber)
    monkeypatch.setattr(voice_app, 'VoiceControlWindow', window)
    monkeypatch.setattr(voice_app, 'QApplication', SimpleNamespace(
        instance=lambda: SimpleNamespace(exec_=lambda: 0)))
    assert voice_app.main([]) == 0
    assert captured['speech'] == {
        'model': 'configured-gemini-model', 'language': 'en',
        'request_timeout_seconds': 12.0,
    }
    assert captured['audio'] == {'sample_rate': 22050, 'max_record_seconds': 7.0}
    assert captured['window']['sample_rate'] == 22050
    assert captured['window']['speech_status'] == 'Gemini API — resolved-gemini-model'


def test_speech_error_does_not_send_navigation_goal(app, tmp_path):
    """A transcription failure must display an error without dispatching Nav2."""
    class FailedTranscriber(Transcriber):

        def transcribe(self, samples, sample_rate):
            raise SpeechModelError('Gemini API request failed')

    widget, backend, recorder, _ = make_window(
        tmp_path, transcriber=FailedTranscriber())
    try:
        QTest.mousePress(widget.record_button, Qt.LeftButton)
        wait_until(app, lambda: recorder.starts == 1)
        QTest.mouseRelease(widget.record_button, Qt.LeftButton)
        wait_until(app, lambda: 'model_error' in widget.error_label.text())
        assert 'Gemini API request failed' in widget.error_label.text()
        assert 'Có lỗi' in widget.status_label.text()
        assert backend.calls == []
        assert widget.transcript_view.toPlainText() == ''
    finally:
        widget.close()
        wait_until(app, lambda: not widget.isVisible())


@pytest.mark.parametrize('provider', [None, 'whisper', 'Gemini', 'gemini '])
def test_main_rejects_non_gemini_provider_before_ros(tmp_path, monkeypatch, provider):
    """Unsupported providers must fail before starting external runtime resources."""
    import rclpy
    from tb4_voice_control import voice_app

    semantic, occupancy = runtime_map(tmp_path)
    config_path = tmp_path / 'voice.yaml'
    config_path.write_text(yaml.safe_dump({'provider': provider}))
    monkeypatch.setattr(voice_app, '_parse_runtime_arguments', lambda argv: (
        SimpleNamespace(regions='regions', voice_config=config_path), []))
    monkeypatch.setattr(voice_app, 'load_regions', lambda path: semantic)
    monkeypatch.setattr(voice_app, 'load_occupancy_map', lambda path: occupancy)
    calls = []

    def initialize_ros(**kwargs):
        calls.append('ROS initialized')
        pytest.fail('Unsupported provider reached ROS initialization')

    monkeypatch.setattr(rclpy, 'init', initialize_ros)
    with pytest.raises(ValueError, match='provider.*gemini'):
        voice_app.main([])
    assert calls == []


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


def test_queued_close_retry_after_success_shuts_ros_down_once(app, tmp_path, monkeypatch):
    """An already-queued retry cannot finalize a second successful close again."""
    backend = CleanupBackend()
    backend.cleanup_state = CleanupState.QUIESCENT
    original_execute = backend.execute

    def execute(*args):
        backend.cleanup_state = CleanupState.PENDING
        return original_execute(*args)

    backend.execute = execute
    widget, _, _, shutdown_calls = make_window(
        tmp_path, backend=backend, shutdown_timeout_ms=20)
    queued = []
    single_shot = QTimer.singleShot
    monkeypatch.setattr(QTimer, 'singleShot', lambda delay, callback: queued.append(callback))
    try:
        widget._controller.process_text('Đi đến B')
        wait_until(app, lambda: widget._controller.state.value == 'cleaning')
        assert not widget.close()
        assert len(queued) == 1
        assert shutdown_calls == []
        backend.resolve()
        assert widget._controller.wait(2)
        assert widget._navigation_thread.wait(2000)
        wait_until(app, lambda: not widget._speech_thread.isRunning())
        assert widget.close()
        assert shutdown_calls == [True]
        single_shot(0, queued.pop())
        app.processEvents()
        assert shutdown_calls == [True]
    finally:
        backend.resolve()
        widget.close()


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


def test_cleanup_pending_keeps_controls_disabled_and_close_deferred(app, tmp_path):
    """An unresolved cleanup keeps the real window and ROS alive."""
    backend = CleanupBackend()
    backend.cleanup_state = CleanupState.QUIESCENT
    original = backend.execute

    def execute(*args):
        backend.cleanup_state = CleanupState.PENDING
        return original(*args)

    backend.execute = execute
    widget, _, _, shutdown_calls = make_window(
        tmp_path, backend=backend, shutdown_timeout_ms=20)
    try:
        widget.text_input.setText('Đi đến B')
        QTest.mouseClick(widget.send_button, Qt.LeftButton)
        wait_until(app, lambda: widget._controller.state.value == 'cleaning')
        app.processEvents()
        assert not widget.record_button.isEnabled()
        assert not widget.text_input.isEnabled()
        assert not widget.send_button.isEnabled()
        assert not widget.cancel_button.isEnabled()
        assert not widget.close()
        assert shutdown_calls == []
        assert widget.isVisible()
    finally:
        backend.resolve()
        widget.close()
        wait_until(app, lambda: shutdown_calls == [True])


def test_force_abort_requires_warning_and_never_reenables_navigation(
        app, tmp_path, monkeypatch):
    """Declining the warning keeps cleanup alive; confirmation permits close."""
    backend = CleanupBackend()
    backend.cleanup_state = CleanupState.QUIESCENT
    original = backend.execute

    def execute(*args):
        backend.cleanup_state = CleanupState.PENDING
        return original(*args)

    backend.execute = execute
    widget, _, _, shutdown_calls = make_window(
        tmp_path, backend=backend, shutdown_timeout_ms=20)
    choices = iter((QMessageBox.No, QMessageBox.Yes))
    warnings = []

    def choose(parent, title, message, *args):
        warnings.append(message)
        return next(choices)

    monkeypatch.setattr(QMessageBox, 'warning', choose)
    try:
        widget.text_input.setText('Đi đến B')
        QTest.mouseClick(widget.send_button, Qt.LeftButton)
        wait_until(app, lambda: widget._controller.state.value == 'cleaning')
        wait_until(app, lambda: widget.force_abort_button.isVisible())
        QTest.mouseClick(widget.force_abort_button, Qt.LeftButton)
        assert backend.cleanup_state is CleanupState.PENDING
        assert 'chưa' in warnings[0].lower()
        assert not widget.close()
        assert shutdown_calls == []
        QTest.mouseClick(widget.force_abort_button, Qt.LeftButton)
        wait_until(app, lambda: backend.cleanup_state is CleanupState.FORCE_ABORTED)
        wait_until(app, lambda: widget._controller.state.value == 'error')
        app.processEvents()
        assert not widget.record_button.isEnabled()
        assert not widget.text_input.isEnabled()
        widget._controller.process_text('Đi đến B')
        assert backend.calls == ['b']
        wait_until(app, lambda: shutdown_calls == [True])
    finally:
        backend.resolve()
        widget.close()
        wait_until(app, lambda: shutdown_calls == [True])


def test_cleanup_resolves_during_warning_then_next_cleanup_can_be_forced(
        app, tmp_path, monkeypatch):
    """A stale confirmation must not disable force on the next cleanup."""
    backend = CleanupBackend()
    backend.cleanup_state = CleanupState.QUIESCENT

    def execute(region, cancel_event, on_progress):
        backend.calls.append(region.id)
        backend.release.clear()
        backend.cleanup_state = CleanupState.PENDING
        return RouteState.FAILED

    backend.execute = execute
    widget, _, _, shutdown_calls = make_window(
        tmp_path, backend=backend, shutdown_timeout_ms=20)
    warnings = []

    def choose(parent, title, message, *args):
        warnings.append(message)
        if len(warnings) == 1:
            backend.resolve()
            assert widget._controller.wait(2)
            app.processEvents()
        return QMessageBox.Yes

    monkeypatch.setattr(QMessageBox, 'warning', choose)
    try:
        widget.text_input.setText('Đi đến B')
        QTest.mouseClick(widget.send_button, Qt.LeftButton)
        wait_until(app, lambda: widget.force_abort_button.isVisible())
        QTest.mouseClick(widget.force_abort_button, Qt.LeftButton)
        wait_until(app, lambda: widget.record_button.isEnabled())
        QTest.mouseClick(widget.send_button, Qt.LeftButton)
        wait_until(app, lambda: len(backend.calls) == 2)
        wait_until(app, lambda: widget.force_abort_button.isVisible())
        assert widget.force_abort_button.isEnabled()
        assert not widget.close()
        assert shutdown_calls == []
        QTest.mouseClick(widget.force_abort_button, Qt.LeftButton)
        wait_until(app, lambda: shutdown_calls == [True])
        assert backend.cleanup_state is CleanupState.FORCE_ABORTED
        assert len(warnings) == 2
        widget.shutdown()
        assert shutdown_calls == [True]
    finally:
        backend.resolve()
        widget.close()
        wait_until(app, lambda: shutdown_calls == [True])


def test_rejected_force_request_restores_cleanup_button(app, tmp_path, monkeypatch):
    """A rejected force request leaves the pending cleanup actionable."""
    backend = CleanupBackend()
    backend.cleanup_state = CleanupState.QUIESCENT
    entered = threading.Event()
    release = threading.Event()
    original = backend.execute

    def execute(*args):
        backend.cleanup_state = CleanupState.PENDING
        return original(*args)

    def reject_force():
        entered.set()
        assert release.wait(2)
        return False

    backend.execute = execute
    backend.force_abort_cleanup = reject_force
    widget, _, _, shutdown_calls = make_window(tmp_path, backend=backend)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.Yes)
    try:
        widget.text_input.setText('Đi đến B')
        QTest.mouseClick(widget.send_button, Qt.LeftButton)
        wait_until(app, lambda: widget.force_abort_button.isVisible())
        QTest.mouseClick(widget.force_abort_button, Qt.LeftButton)
        assert entered.wait(2)
        assert not widget.force_abort_button.isEnabled()
        release.set()
        wait_until(app, lambda: widget.force_abort_button.isEnabled())
        assert backend.cleanup_state is CleanupState.PENDING
    finally:
        release.set()
        backend.resolve()
        widget.close()
        wait_until(app, lambda: shutdown_calls == [True])
