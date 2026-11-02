"""Orchestrate Vietnamese text to semantic Nav2 routes without a UI."""

from dataclasses import dataclass
from enum import Enum
import logging
import threading
from typing import Callable

from tb4_voice_control.command_parser import CommandError, parse_command
from tb4_voice_control.map_model import OccupancyMap
from tb4_voice_control.regions import GoalPose, SemanticMap
from tb4_voice_control.route_executor import RouteExecutor, RouteState
from tb4_voice_control.route_planner import find_current_region, plan_route


class RuntimeState(str, Enum):
    """User-facing command lifecycle independent of Qt and ROS."""

    IDLE = 'idle'
    NAVIGATING = 'navigating'
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
        """Build the executor and retain injectable external boundaries."""
        if pose_poll_timeout < 0:
            raise ValueError('pose_poll_timeout must not be negative')
        self.semantic_map = semantic_map
        self.occupancy = occupancy
        self._navigation_backend = navigation_backend
        self._pose_poll_timeout = pose_poll_timeout
        self._current_pose = current_pose or self._poll_current_pose
        self._listeners = {name: [] for name in self.EVENTS}
        self._listener_lock = threading.Lock()
        self._command_lock = threading.Lock()
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
        return self.state is RuntimeState.NAVIGATING

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
        with self._command_lock:
            if not self._accepting:
                return
            self._emit('transcript', transcript)
            if self.is_busy:
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
            try:
                current_id = self._current_region_id()
            except Exception as error:  # noqa: B902 - injected pose boundary
                self._report_error('localization_error',
                                   f'Không đọc được vị trí robot: {error}')
                return
            route = plan_route(command, current_id)
            self._emit('route', route)
            if not route:
                self._set_state(RuntimeState.SUCCEEDED)
                return

            self._set_state(RuntimeState.NAVIGATING)
            try:
                accepted = self._executor.start(route)
            except Exception as error:  # noqa: B902 - executor boundary
                self._report_error('nav2_error',
                                   f'Không thể gửi lộ trình tới Nav2: {error}')
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
        with self._command_lock:
            if self._accepting:
                self._report_error(code, message, preserve_state=self.is_busy)

    def close_admission(self) -> None:
        """Synchronize with command planning, then reject all future work."""
        with self._command_lock:
            self._accepting = False

    def cancel(self) -> None:
        """Cancel cooperatively; the executor owns terminal state."""
        self._executor.cancel()

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
            return None
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
        elif route_state is RouteState.SUCCEEDED:
            self._set_state(RuntimeState.SUCCEEDED)
        elif route_state is RouteState.CANCELED:
            self._set_state(RuntimeState.CANCELED)
        elif route_state is RouteState.FAILED:
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
