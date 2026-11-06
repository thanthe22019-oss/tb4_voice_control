"""Vietnamese push-to-talk runtime window for semantic Nav2 navigation."""

import argparse
from pathlib import Path
import sys
import threading

from PyQt5.QtCore import pyqtSignal, QThread, QTimer
from PyQt5.QtWidgets import (
    QApplication, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget)

from tb4_voice_control.audio_capture import AudioRecorder
from tb4_voice_control.command_parser import Intent
from tb4_voice_control.map_model import load_occupancy_map
from tb4_voice_control.qt_workers import NavigationWorker, SpeechWorker
from tb4_voice_control.region_validation import validate_semantic_map
from tb4_voice_control.regions import load_regions
from tb4_voice_control.route_executor import LegProgress
from tb4_voice_control.runtime_controller import (
    RuntimeController, RuntimeErrorInfo, RuntimeState)
from tb4_voice_control.speech import WhisperTranscriber
import yaml


class VoiceControlWindow(QMainWindow):
    """Display command stages while keeping external work off the UI thread."""

    start_recording_requested = pyqtSignal()
    stop_recording_requested = pyqtSignal()
    text_requested = pyqtSignal(str)
    cancel_requested = pyqtSignal()
    adapter_error = pyqtSignal(str, str)
    speech_shutdown_requested = pyqtSignal()

    def __init__(self, controller: RuntimeController, recorder, transcriber, *,
                 sample_rate: int = 16000,
                 connection_status: str = 'Nav2 chưa kiểm tra',
                 gpu_status: str = 'GPU chưa kiểm tra', shutdown_ros=None,
                 shutdown_timeout_ms: int = 2000):
        """Construct widgets and two worker loops with injected adapters."""
        super().__init__()
        self._controller = controller
        self._shutdown_ros = shutdown_ros or (lambda: None)
        self._shutdown_timeout_ms = max(1, int(shutdown_timeout_ms))
        self._shutdown_started = False
        self._shutdown_done = False
        self._shutdown_retry_pending = False
        self._region_names = {
            region.id: region.name
            for region in controller.semantic_map.regions
        }
        self.setWindowTitle('TurtleBot 4 — Điều hướng bằng giọng nói')
        self.resize(760, 640)

        self.connection_label = QLabel(connection_status)
        self.gpu_label = QLabel(gpu_status)
        self.transcript_view = QTextEdit()
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setPlaceholderText(
            'Bản ghi giọng nói sẽ xuất hiện ở đây')
        self.intent_label = QLabel('Chưa có lệnh')
        self.route_list = QLabel('Chưa có lộ trình')
        self.route_list.setWordWrap(True)
        self.leg_label = QLabel('Chưa có chặng đang chạy')
        self.progress_label = QLabel('Chưa có phản hồi Nav2')
        self.status_label = QLabel('Sẵn sàng nhận lệnh')
        self.error_label = QLabel('')
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet('color: #b00020;')
        self.valid_regions_label = QLabel(
            ', '.join(controller.valid_region_names))
        self.valid_regions_label.setWordWrap(True)

        self.record_button = QPushButton('Giữ để nói')
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText('Ví dụ: Đi đến phòng thí nghiệm')
        self.send_button = QPushButton('Gửi lệnh văn bản')
        self.cancel_button = QPushButton('Hủy lộ trình')
        self.cancel_button.setEnabled(False)
        self.force_abort_button = QPushButton('Buộc dừng chờ Nav2')
        self.force_abort_button.hide()

        root = QWidget()
        layout = QVBoxLayout(root)
        status_group = QGroupBox('Trạng thái hệ thống')
        status_form = QFormLayout(status_group)
        status_form.addRow('Kết nối:', self.connection_label)
        status_form.addRow('GPU / mô hình:', self.gpu_label)
        status_form.addRow('Khu vực hợp lệ:', self.valid_regions_label)
        layout.addWidget(status_group)
        layout.addWidget(QLabel('Transcript'))
        layout.addWidget(self.transcript_view)
        command_group = QGroupBox('Lệnh và lộ trình')
        command_form = QFormLayout(command_group)
        command_form.addRow('Intent:', self.intent_label)
        command_form.addRow('Hàng đợi:', self.route_list)
        command_form.addRow('Chặng hiện tại:', self.leg_label)
        command_form.addRow('Tiến độ:', self.progress_label)
        command_form.addRow('Kết quả:', self.status_label)
        command_form.addRow('Lỗi:', self.error_label)
        layout.addWidget(command_group)
        controls = QHBoxLayout()
        controls.addWidget(self.record_button)
        controls.addWidget(self.cancel_button)
        controls.addWidget(self.force_abort_button)
        layout.addLayout(controls)
        text_controls = QHBoxLayout()
        text_controls.addWidget(self.text_input, 1)
        text_controls.addWidget(self.send_button)
        layout.addLayout(text_controls)
        self.setCentralWidget(root)

        self._speech_thread = QThread(self)
        self._speech_worker = SpeechWorker(recorder, transcriber, sample_rate)
        self._speech_worker.moveToThread(self._speech_thread)
        self.start_recording_requested.connect(
            self._speech_worker.start_recording)
        self.stop_recording_requested.connect(
            self._speech_worker.stop_and_transcribe)
        self.speech_shutdown_requested.connect(self._speech_worker.shutdown)
        self._speech_worker.transcript.connect(self.text_requested.emit)
        self._speech_worker.error.connect(self.adapter_error.emit)
        self._speech_worker.recording_changed.connect(self._recording_changed)
        self._speech_thread.start()

        self._navigation_thread = QThread(self)
        self._navigation_worker = NavigationWorker(controller)
        self._navigation_worker.moveToThread(self._navigation_thread)
        self.text_requested.connect(self._navigation_worker.process_text)
        self.cancel_requested.connect(self._navigation_worker.cancel)
        self.adapter_error.connect(self._navigation_worker.report_error)
        self._navigation_worker.transcript.connect(self._show_transcript)
        self._navigation_worker.command.connect(self._show_command)
        self._navigation_worker.route.connect(self._show_route)
        self._navigation_worker.state.connect(self._show_state)
        self._navigation_worker.progress.connect(self._show_progress)
        self._navigation_worker.error.connect(self._show_error)
        self._navigation_thread.start()

        self.record_button.pressed.connect(self.start_recording_requested.emit)
        self.record_button.released.connect(self.stop_recording_requested.emit)
        self.send_button.clicked.connect(self._submit_text)
        self.text_input.returnPressed.connect(self._submit_text)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.force_abort_button.clicked.connect(self._force_abort)

    def _force_abort(self):
        if QMessageBox.warning(
                self, 'Chưa xác nhận hủy',
                'Nav2 chưa xác nhận hủy từ xa. Buộc dừng sẽ khóa điều hướng '
                'trong phiên này. Tiếp tục?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.force_abort_button.setEnabled(False)
        threading.Thread(target=self._controller.force_abort_cleanup,
                         daemon=True).start()

    def _submit_text(self):
        self.text_requested.emit(self.text_input.text())

    def _recording_changed(self, recording):
        label = 'Thả để nhận dạng' if recording else 'Giữ để nói'
        self.record_button.setText(label)
        if recording:
            self.status_label.setText('Đang thu âm...')

    def _show_transcript(self, text):
        self.transcript_view.setPlainText(text)
        self.error_label.clear()

    def _show_command(self, command):
        destination = self._region_names.get(command.destination_id,
                                             command.destination_id)
        if command.intent is Intent.GO_TO:
            text = f'GO_TO — đi đến {destination}'
        else:
            source = self._region_names.get(
                command.source_id, command.source_id)
            text = f'FROM_TO — từ {source} đến {destination}'
        self.intent_label.setText(text)

    def _show_route(self, route):
        names = [self._region_names.get(identifier, identifier)
                 for identifier in route]
        text = ' → '.join(names) if names else 'Robot đã ở đích'
        self.route_list.setText(text)

    def _show_progress(self, progress: LegProgress):
        name = self._region_names.get(progress.region_id, progress.region_id)
        self.leg_label.setText(
            f'{progress.leg_index}/{progress.leg_count}: {name}')
        details = []
        if progress.distance_remaining is not None:
            details.append(f'còn {progress.distance_remaining:.2f} m')
        if progress.elapsed_seconds is not None:
            details.append(f'{progress.elapsed_seconds:.1f} s')
        self.progress_label.setText(
            ' — '.join(details) or 'Đang gửi goal tới Nav2')

    def _show_state(self, state: RuntimeState):
        navigating = state is RuntimeState.NAVIGATING
        busy = (navigating or state is RuntimeState.CLEANING
                or self._shutdown_started or self._controller.navigation_disabled)
        self.record_button.setEnabled(not busy)
        self.text_input.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.cancel_button.setEnabled(navigating)
        self.force_abort_button.setVisible(state is RuntimeState.CLEANING)
        labels = {
            RuntimeState.IDLE: 'Sẵn sàng nhận lệnh',
            RuntimeState.NAVIGATING: 'Robot đang di chuyển',
            RuntimeState.CLEANING: 'Đang chờ Nav2 xác nhận xử lý hủy',
            RuntimeState.SUCCEEDED: 'Điều hướng thành công',
            RuntimeState.CANCELED: 'Đã hủy lộ trình',
            RuntimeState.ERROR: 'Có lỗi — chưa gửi thêm goal',
        }
        self.status_label.setText(labels[state])

    def _show_error(self, error: RuntimeErrorInfo):
        valid = ', '.join(error.valid_regions)
        suffix = f' Khu vực hợp lệ: {valid}.' if valid else ''
        self.error_label.setText(f'[{error.code}] {error.message}{suffix}')

    def shutdown(self):
        """Stop admission and finalize only after every owned worker exits."""
        if self._shutdown_done:
            return True
        if not self._shutdown_started:
            self._shutdown_started = True
            self.record_button.setEnabled(False)
            self.text_input.setEnabled(False)
            self.send_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
            self._speech_worker.close_admission()
            self._navigation_worker.close_admission()
            self.speech_shutdown_requested.emit()
            self._controller.cancel()
            self._navigation_thread.quit()
        return self._try_finish_shutdown(wait=True)

    def _try_finish_shutdown(self, *, wait=False):
        """Use bounded waits, deferring close until all owned work is gone."""
        wait_seconds = self._shutdown_timeout_ms / 1000.0 if wait else 0.0
        wait_ms = self._shutdown_timeout_ms if wait else 0
        route_stopped = self._controller.wait(wait_seconds)
        navigation_stopped = (
            not self._navigation_thread.isRunning()
            or self._navigation_thread.wait(wait_ms))
        speech_stopped = (
            not self._speech_thread.isRunning()
            or self._speech_thread.wait(wait_ms))
        if route_stopped and navigation_stopped and speech_stopped:
            self._navigation_worker.detach()
            self._shutdown_ros()
            self._shutdown_done = True
            self._shutdown_retry_pending = False
            return True
        self.status_label.setText(
            'Đang chờ tác vụ nền dừng an toàn trước khi đóng...')
        if not self._shutdown_retry_pending:
            self._shutdown_retry_pending = True
            QTimer.singleShot(20, self._retry_shutdown)
        return False

    def _retry_shutdown(self):
        self._shutdown_retry_pending = False
        if self._try_finish_shutdown():
            self.close()

    def closeEvent(self, event):
        """Clean up the process before accepting window close."""
        if self.shutdown():
            event.accept()
        else:
            event.ignore()


def _default_config_path(filename):
    """Resolve installed data first and retain source-checkout usability."""
    try:
        from ament_index_python.packages import get_package_share_directory

        share = Path(get_package_share_directory('tb4_voice_control'))
        return share / 'config' / filename
    except Exception:  # noqa: B902 - source checkout fallback
        return Path(__file__).resolve().parents[1] / 'config' / filename


def _parse_runtime_arguments(argv=None):
    """Parse application options while preserving ROS arguments for rclpy."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regions', type=Path,
                        default=_default_config_path('regions.yaml'))
    parser.add_argument('--voice-config', type=Path,
                        default=_default_config_path('voice.yaml'))
    ros_arguments = (list(sys.argv) if argv is None
                     else [sys.argv[0], *argv])
    from rclpy.utilities import remove_ros_args

    application_arguments = remove_ros_args(ros_arguments)[1:]
    return parser.parse_args(application_arguments), ros_arguments


def _validate_runtime_map(semantic_map, occupancy):
    issues = validate_semantic_map(semantic_map, occupancy)
    if issues:
        details = '; '.join(f'{issue.region_id or "map"}: {issue.code}: {issue.message}'
                            for issue in issues)
        raise ValueError(f'Invalid region configuration: {details}')


def main(argv=None):
    """Initialize ROS and speech only for the console runtime."""
    arguments, ros_arguments = _parse_runtime_arguments(argv)
    semantic_map = load_regions(arguments.regions)
    occupancy = load_occupancy_map(semantic_map.map_yaml)
    _validate_runtime_map(semantic_map, occupancy)
    with arguments.voice_config.open(encoding='utf-8') as stream:
        config = yaml.safe_load(stream) or {}

    import rclpy
    from tb4_voice_control.nav2_backend import BasicNavigatorBackend

    rclpy.init(args=ros_arguments)
    backend = BasicNavigatorBackend(frame_id=semantic_map.frame_id)
    controller = RuntimeController(semantic_map, occupancy, backend)
    recorder = AudioRecorder(
        sample_rate=int(config.get('sample_rate', 16000)),
        max_record_seconds=float(config.get('max_record_seconds', 15)),
    )
    transcriber = WhisperTranscriber(
        model_size=str(config.get('model_size', 'small')),
        device=str(config.get('device', 'cuda')),
        compute_type=str(config.get('compute_type', 'float16')),
        language=str(config.get('language', 'vi')),
    )
    app = QApplication.instance() or QApplication([sys.argv[0]])
    closed = False

    def shutdown_ros():
        nonlocal closed
        if closed:
            return
        closed = True
        backend.navigator.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    window = VoiceControlWindow(
        controller, recorder, transcriber,
        sample_rate=recorder.sample_rate,
        connection_status='Nav2: chờ localization / action server',
        gpu_status=(f'{transcriber.device.upper()} — {transcriber.model_size} '
                    f'({transcriber.compute_type})'),
        shutdown_ros=shutdown_ros,
    )
    window.show()
    result = app.exec_()
    window.shutdown()
    return result


if __name__ == '__main__':
    raise SystemExit(main())
