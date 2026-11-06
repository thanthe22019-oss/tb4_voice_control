"""Orchestrate Vietnamese text to semantic Nav2 routes without a UI."""

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import logging
import threading
from typing import Callable

from tb4_voice_control.command_parser import CommandError, parse_command
from tb4_voice_control.map_model import OccupancyMap
from tb4_voice_control.regions import GoalPose, SemanticMap
from tb4_voice_control.route_executor import CleanupState, RouteExecutor, RouteState
from tb4_voice_control.route_planner import find_current_region, plan_route


class RuntimeState(str, Enum):
    """User-facing command lifecycle independent of Qt and ROS."""

    IDLE = 'idle'
    NAVIGATING = 'navigating'
    CLEANING = 'cleaning'
    SUCCEEDED = 'succeeded'
    CANCELED = 'canceled'
    ERROR = 'error'


@dataclass(frozen=True)
class RuntimeErrorInfo:
    """A typed error plus the region catalog needed to recover from it."""

    code: str
    message: str
    valid_regions: tuple[str, ...] = ()


class RuntimeController:
    """Apply one deterministic parser/planner/executor pipeline to all text."""

    EVENTS = ('transcript', 'command', 'route', 'state', 'progress', 'error')

    def __init__(self, semantic_map: SemanticMap, occupancy: OccupancyMap,
                 navigation_backend, *,
                 current_pose: Callable[[], GoalPose | None] | None = None,
                 executor_factory=RouteExecutor,
                 pose_poll_timeout: float = 0.05):
        """Build the executor; callers must validate the semantic map against occupancy."""
        if pose_poll_timeout < 0:
            raise ValueError('pose_poll_timeout must not be negative')
        self.semantic_map = semantic_map
        self.occupancy = occupancy
        self._navigation_backend = navigation_backend
        self._pose_poll_timeout = pose_poll_timeout
        self._current_pose = current_pose or self._poll_current_pose
        self._listeners = {name: [] for name in self.EVENTS}
        self._listener_lock = threading.Lock()
        self._processing_lock = threading.Condition()
        self._processing_owner = None
        self._processing_depth = 0
        self._admission = threading.Condition()
        self._inflight = {}
        self._state_lock = threading.Lock()
        self._state = RuntimeState.IDLE
        self._accepting = True
        self._executor = executor_factory(
            navigation_backend, semantic_map.regions,
            on_state=self._route_state_changed,
            on_progress=lambda progress: self._emit('progress', progress),
        )

    @property
    def state(self) -> RuntimeState:
        """Read the current user-facing state safely from any UI worker."""
        with self._state_lock:
            return self._state

    @property
    def is_busy(self) -> bool:
        """Return whether command admission must remain disabled."""
        return self.state in (RuntimeState.NAVIGATING, RuntimeState.CLEANING)

    @property
    def navigation_disabled(self) -> bool:
        """Report permanent navigation lockout after forced cleanup."""
        return getattr(self._executor, 'cleanup_state', None) is CleanupState.FORCE_ABORTED

    @property
    def valid_region_names(self) -> tuple[str, ...]:
        """Expose display names for UI guidance and parser recovery."""
        return tuple(region.name for region in self.semantic_map.regions)

    def add_listener(self, event: str,
                     callback: Callable) -> Callable[[], None]:
        """Subscribe to an event and return an idempotent unsubscribe."""
        if event not in self._listeners:
            raise ValueError(f'Unknown runtime event: {event}')
        with self._listener_lock:
            self._listeners[event].append(callback)
        removed = threading.Event()

        def unsubscribe():
            if removed.is_set():
                return
            removed.set()
            with self._listener_lock:
                if callback in self._listeners[event]:
                    self._listeners[event].remove(callback)

        return unsubscribe

    def process_text(self, text: str) -> None:
        """Process diagnostic or speech text through one route path."""
        transcript = str(text or '').strip()
        with self._serialized_processing():
            if not self._begin_operation():
                return
            try:
                self._process_admitted_text(transcript)
            finally:
                self._finish_operation()

    def _process_admitted_text(self, transcript):
        """Run one admitted command with callbacks outside admission state."""
        if not self._admission_open():
            return
        if self.navigation_disabled:
            self._report_error('cleanup_aborted',
                               'Chưa xác nhận hủy từ xa; điều hướng đã bị khóa.')
            return
        self._emit('transcript', transcript)
        if not self._admission_open():
            return
        if self.is_busy:
            if self.state is RuntimeState.CLEANING:
                self._report_error(
                    'cleanup_pending',
                    'Nav2 đang xử lý hủy; hãy chờ xác nhận trước khi gửi lệnh.',
                    preserve_state=True)
                return
            self._report_error(
                'route_active',
                'Một lộ trình đang chạy; hãy chờ hoàn tất '
                'hoặc nhấn Hủy.',
                preserve_state=True,
            )
            return
        if not transcript:
            self._report_error('empty_transcript',
                               'Không nhận được nội dung câu lệnh.')
            return
        try:
            command = parse_command(transcript, self.semantic_map)
        except CommandError as error:
            self._report_error(error.code, str(error))
            return
        self._emit('command', command)
        if not self._admission_open():
            return
        try:
            current_id = self._current_region_id()
        except Exception as error:  # noqa: B902 - injected pose boundary
            self._report_error('localization_error',
                               f'Không đọc được vị trí robot: {error}')
            return
        route = plan_route(command, current_id)
        self._emit('route', route)
        if not self._admission_open():
            return
        if not route:
            self._set_state(RuntimeState.SUCCEEDED)
            return

        self._set_state(RuntimeState.NAVIGATING)
        if not self._admission_open():
            self._set_state(RuntimeState.CANCELED)
            return
        try:
            accepted = self._executor.start(route)
        except Exception as error:  # noqa: B902 - executor boundary
            self._report_error('nav2_error',
                               f'Không thể gửi lộ trình tới Nav2: {error}')
            return
        if not self._admission_open():
            self._executor.cancel()
            return
        if not accepted:
            self._report_error(
                'route_active',
                'Một lộ trình đang chạy; hãy chờ hoàn tất '
                'hoặc nhấn Hủy.',
                preserve_state=True,
            )

    def process_transcript(self, text: str) -> None:
        """Name the speech entry while deliberately sharing process_text."""
        self.process_text(text)

    def report_error(self, code: str, message: str) -> None:
        """Publish microphone/model errors without ever creating a route."""
        with self._serialized_processing():
            if not self._begin_operation():
                return
            try:
                self._report_error(code, message, preserve_state=self.is_busy)
            finally:
                self._finish_operation()

    @contextmanager
    def _serialized_processing(self):
        """Serialize command processing without holding a lock in callbacks."""
        current = threading.get_ident()
        with self._processing_lock:
            while self._processing_owner not in (None, current):
                self._processing_lock.wait()
            self._processing_owner = current
            self._processing_depth += 1
        try:
            yield
        finally:
            with self._processing_lock:
                self._processing_depth -= 1
                if not self._processing_depth:
                    self._processing_owner = None
                    self._processing_lock.notify_all()

    def close_admission(self) -> None:
        """Reject new work and wait for every other admitted caller."""
        current = threading.get_ident()
        with self._admission:
            self._accepting = False
            while sum(self._inflight.values()) > self._inflight.get(current, 0):
                self._admission.wait()

    def _begin_operation(self):
        current = threading.get_ident()
        with self._admission:
            if not self._accepting:
                return False
            self._inflight[current] = self._inflight.get(current, 0) + 1
            return True

    def _finish_operation(self):
        current = threading.get_ident()
        with self._admission:
            remaining = self._inflight[current] - 1
            if remaining:
                self._inflight[current] = remaining
            else:
                del self._inflight[current]
            self._admission.notify_all()

    def _admission_open(self):
        with self._admission:
            return self._accepting

    def cancel(self) -> None:
        """Cancel cooperatively; the executor owns terminal state."""
        self._executor.cancel()

    def force_abort_cleanup(self) -> bool:
        """Explicitly abandon local cleanup and retain an indeterminate error."""
        if self.state is not RuntimeState.CLEANING:
            return False
        aborted = self._executor.force_abort_cleanup()
        if aborted:
            self._report_error('cleanup_aborted',
                               'Chưa xác nhận hủy từ xa; điều hướng đã bị khóa.')
        return aborted

    def wait(self, timeout: float | None = None) -> bool:
        """Bound shutdown joins using the executor's non-recursive wait API."""
        return self._executor.wait(timeout)

    def shutdown(self, timeout: float = 2.0) -> bool:
        """Request cancellation and wait no longer than the caller's budget."""
        self.cancel()
        return self.wait(timeout)

    def _current_region_id(self) -> str | None:
        pose = self._current_pose()
        if pose is None:
            raise ValueError('Chưa nhận được /amcl_pose; '
                             'đặt vị trí ban đầu trong RViz và thử lại.')
        if hasattr(pose, 'x') and hasattr(pose, 'y'):
            point = (pose.x, pose.y)
        else:
            point = (pose[0], pose[1])
        region = find_current_region(point, self.semantic_map, self.occupancy)
        return region.id if region is not None else None

    def _poll_current_pose(self):
        poll = getattr(self._navigation_backend, 'poll_pose', None)
        if poll is not None:
            return poll(timeout=self._pose_poll_timeout)
        return getattr(self._navigation_backend, 'current_pose', None)

    def _route_state_changed(self, route_state: RouteState) -> None:
        if route_state is RouteState.RUNNING:
            self._set_state(RuntimeState.NAVIGATING)
        elif route_state is RouteState.CLEANING:
            self._set_state(RuntimeState.CLEANING)
        elif route_state is RouteState.SUCCEEDED:
            self._set_state(RuntimeState.SUCCEEDED)
        elif route_state is RouteState.CANCELED:
            self._set_state(RuntimeState.CANCELED)
        elif route_state is RouteState.FAILED:
            if self.navigation_disabled:
                self._report_error('cleanup_aborted',
                                   'Chưa xác nhận hủy từ xa; điều hướng đã bị khóa.')
            else:
                self._report_error('nav2_failed',
                                   'Nav2 không hoàn thành được lộ trình.')

    def _set_state(self, state: RuntimeState) -> None:
        with self._state_lock:
            self._state = state
        self._emit('state', state)

    def _report_error(self, code: str, message: str, *,
                      preserve_state: bool = False) -> None:
        error = RuntimeErrorInfo(code, message, self.valid_region_names)
        self._emit('error', error)
        if not preserve_state:
            self._set_state(RuntimeState.ERROR)

    def _emit(self, event: str, value) -> None:
        with self._listener_lock:
            callbacks = tuple(self._listeners[event])
        for callback in callbacks:
            try:
                callback(value)
            except Exception:  # noqa: B902 - observers cannot own runtime
                logging.getLogger(__name__).exception(
                    'Runtime %s callback failed', event)
