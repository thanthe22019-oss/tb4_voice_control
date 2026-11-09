"""Exercise the complete text-to-route runtime without ROS, Qt, or hardware."""

import threading

import numpy as np
import pytest

from tb4_voice_control.command_parser import Intent
from tb4_voice_control.map_model import MapMetadata, OccupancyMap
from tb4_voice_control.regions import GoalPose, Region, SemanticMap
from tb4_voice_control.route_executor import CleanupState, RouteState
from tb4_voice_control.runtime_controller import (
    RuntimeController, RuntimeErrorInfo, RuntimeState)


def runtime_map(tmp_path):
    """Return two disjoint regions on an all-free identity map."""
    metadata = MapMetadata(tmp_path / 'map.yaml', tmp_path / 'map.pgm', 1.0,
                           (0.0, 0.0, 0.0), False, 0.65, 0.2, 'trinary')
    image = np.full((10, 10), 255, dtype=np.uint8)
    free = np.ones_like(image, dtype=bool)
    blocked = np.zeros_like(image, dtype=bool)
    occupancy = OccupancyMap(metadata, image, free, blocked, blocked.copy())
    regions = (
        Region('a', 'Khu vực A', ('A', 'khu vực A'), (1, 2, 3),
               ((0, 5), (4, 5), (4, 9), (0, 9)), GoalPose(2.0, 2.0, 0.0)),
        Region('b', 'Phòng thí nghiệm', ('B', 'phòng thí nghiệm'),
               (4, 5, 6), ((5, 0), (9, 0), (9, 4), (5, 4)),
               GoalPose(7.0, 7.0, 0.0)),
    )
    return SemanticMap(1, metadata.yaml_path, 'map', regions), occupancy


class Backend:
    """Record dispatch while optionally holding one route active."""

    def __init__(self, block=False, outcome=RouteState.SUCCEEDED):
        """Configure the route result and optional cancellation barrier."""
        self.block = block
        self.outcome = outcome
        self.entered = threading.Event()
        self.calls = []

    def execute(self, region, cancel_event, on_progress):
        """Record a real executor dispatch and cooperatively block if asked."""
        self.calls.append(region.id)
        self.entered.set()
        if self.block:
            cancel_event.wait(2)
            return RouteState.CANCELED
        return self.outcome


class CleanupBackend(Backend):
    """Hold a failed action's cleanup until the test resolves it."""

    def __init__(self):
        super().__init__()
        self.cleanup_state = CleanupState.PENDING
        self.release = threading.Event()

    def execute(self, region, cancel_event, on_progress):
        self.calls.append(region.id)
        self.entered.set()
        return RouteState.FAILED

    def wait_for_cleanup(self, timeout):
        return self.release.wait(timeout)

    def resolve(self):
        self.cleanup_state = CleanupState.QUIESCENT
        self.release.set()

    def force_abort_cleanup(self):
        self.cleanup_state = CleanupState.FORCE_ABORTED
        self.release.set()
        return True


def test_cleanup_state_disables_text_and_sends_zero_second_goals(tmp_path):
    """An unresolved action blocks both text and transcript admission."""
    backend = CleanupBackend()
    backend.cleanup_state = CleanupState.QUIESCENT
    runtime, _, events = controller(tmp_path, backend=backend)
    # Enter PENDING only after the executor accepts the first route.
    original = backend.execute

    def execute(*args):
        backend.cleanup_state = CleanupState.PENDING
        return original(*args)

    backend.execute = execute
    cleaning = threading.Event()
    runtime.add_listener('state', lambda state: cleaning.set()
                         if state.value == 'cleaning' else None)
    runtime.process_text('Đi đến A')
    assert cleaning.wait(2)
    assert runtime.state is RuntimeState.CLEANING
    runtime.process_text('Đi đến B')
    runtime.process_transcript('Đi đến B')
    assert backend.calls == ['a']
    assert 'chờ' in events['error'][-1].message.lower()
    backend.resolve()
    assert runtime.wait(2)


def test_force_abort_is_explicit_and_permanently_rejects_routes(tmp_path):
    """Forced local release must not permit a subsequent Nav2 goal."""
    backend = CleanupBackend()
    backend.cleanup_state = CleanupState.QUIESCENT
    original = backend.execute

    def execute(*args):
        backend.cleanup_state = CleanupState.PENDING
        return original(*args)

    backend.execute = execute
    runtime, _, events = controller(tmp_path, backend=backend)
    cleaning = threading.Event()
    runtime.add_listener('state', lambda state: cleaning.set()
                         if state.value == 'cleaning' else None)
    runtime.process_text('Đi đến A')
    assert cleaning.wait(2)
    assert runtime.force_abort_cleanup()
    assert runtime.wait(2)
    runtime.process_text('Đi đến B')
    assert backend.calls == ['a']
    assert runtime.state is RuntimeState.ERROR
    assert any('chưa' in error.message.lower() for error in events['error'])


def test_confirmed_cleanup_restores_admission_after_failed_route(tmp_path):
    """Confirmed cleanup retains failure while allowing a later route."""
    backend = CleanupBackend()
    backend.cleanup_state = CleanupState.QUIESCENT

    def execute(region, cancel_event, on_progress):
        backend.calls.append(region.id)
        if len(backend.calls) == 1:
            backend.cleanup_state = CleanupState.PENDING
            return RouteState.FAILED
        return RouteState.SUCCEEDED

    backend.execute = execute
    runtime, _, events = controller(tmp_path, backend=backend)
    cleaning = threading.Event()
    runtime.add_listener('state', lambda state: cleaning.set()
                         if state is RuntimeState.CLEANING else None)
    runtime.process_text('Đi đến A')
    assert cleaning.wait(2)
    backend.resolve()
    assert runtime.wait(2)
    assert runtime.state is RuntimeState.ERROR
    assert events['error'][-1].code == 'nav2_failed'
    runtime.process_text('Đi đến B')
    assert runtime.wait(2)
    assert backend.calls == ['a', 'b']
    assert runtime.state is RuntimeState.SUCCEEDED


def test_cleanup_callbacks_do_not_hold_controller_locks(tmp_path):
    """Observers can inspect controller admission locks from another thread."""
    runtime, _, _ = controller(tmp_path)
    results = []

    def check(_):
        def probe():
            for lock in (runtime._processing_lock, runtime._admission):
                acquired = lock.acquire(timeout=0.1)
                results.append(acquired)
                if acquired:
                    lock.release()
        worker = threading.Thread(target=probe)
        worker.start()
        worker.join(1)

    for event in ('transcript', 'state', 'error'):
        runtime.add_listener(event, check)
    runtime.process_text('')
    assert results == [True] * 6


def controller(tmp_path, backend=None, pose=GoalPose(20.0, 20.0, 0.0)):
    """Build one observed controller around deterministic external adapters."""
    semantic, occupancy = runtime_map(tmp_path)
    backend = backend or Backend()
    events = {name: [] for name in RuntimeController.EVENTS}
    instance = RuntimeController(
        semantic, occupancy, backend,
        current_pose=lambda: pose,
    )
    for name in events:
        instance.add_listener(name, events[name].append)
    return instance, backend, events


def test_text_flows_through_parser_planner_and_ordered_executor(tmp_path):
    """Skipping parsing or reversing the route changes visible results."""
    runtime, backend, events = controller(tmp_path)
    runtime.process_text('Di chuyển từ A đến phòng thí nghiệm')
    assert runtime.wait(2)
    assert events['transcript'] == ['Di chuyển từ A đến phòng thí nghiệm']
    assert events['command'][-1].intent is Intent.FROM_TO
    assert events['route'] == [('a', 'b')]
    assert backend.calls == ['a', 'b']
    assert runtime.state is RuntimeState.SUCCEEDED


@pytest.mark.parametrize('outcome, terminal', [
    (RouteState.SUCCEEDED, RuntimeState.SUCCEEDED),
    (RouteState.CANCELED, RuntimeState.CANCELED),
    (RouteState.FAILED, RuntimeState.ERROR),
])
def test_terminal_listener_rejected_command_does_not_strand_runtime(
        tmp_path, outcome, terminal):
    """A still-live terminal worker rejects once without locking out retries."""
    backend = Backend(outcome=outcome)
    runtime, _, events = controller(tmp_path, backend=backend)
    attempts = []

    def submit_during_terminal(state):
        if state is terminal and not attempts:
            attempts.append(state)
            runtime.process_text('Đi đến B')

    runtime.add_listener('state', submit_during_terminal)
    runtime.process_text('Đi đến A')
    assert runtime.wait(2)
    assert attempts == [terminal]
    assert backend.calls == ['a']
    assert events['error'][-1].code == 'route_active'
    assert runtime.state is terminal
    assert not runtime.is_busy

    backend.outcome = RouteState.SUCCEEDED
    runtime.process_text('Đi đến B')
    assert runtime.wait(2)
    assert backend.calls == ['a', 'b']
    assert runtime.state is RuntimeState.SUCCEEDED


def test_current_region_changes_from_to_route_and_suppresses_reached_goal(
        tmp_path):
    """Ignoring AMCL dispatches an unnecessary source or destination."""
    runtime, backend, events = controller(
        tmp_path, pose=GoalPose(2.0, 2.0, 0.0))
    runtime.process_text('Đi từ A đến B')
    assert runtime.wait(2)
    assert events['route'][-1] == ('b',)
    assert backend.calls == ['b']

    runtime.process_text('Đi đến A')
    assert events['route'][-1] == ()
    assert backend.calls == ['b']
    assert runtime.state is RuntimeState.SUCCEEDED


@pytest.mark.parametrize('other_callback_first', [False, True])
def test_production_backend_polls_amcl_before_first_route(
        tmp_path, monkeypatch, other_callback_first):
    """A cached-only first command would resend the source region goal."""
    from geometry_msgs.msg import PoseWithCovarianceStamped

    from tb4_voice_control import nav2_backend
    from tb4_voice_control.nav2_backend import BasicNavigatorBackend

    class Navigator:
        """Expose the real adapter's localization subscription boundary."""

        def create_subscription(self, message, topic, callback, qos):
            """Capture the concrete AMCL callback registered by the adapter."""
            self.pose_callback = callback
            return object()

    executors = []

    class CapturingExecutor:
        """Capture planned IDs without invoking the Nav2 goal boundary."""

        def __init__(self, backend, regions, on_state, on_progress):
            """Retain state callback and planned route evidence."""
            self.on_state = on_state
            self.routes = []
            executors.append(self)

        def start(self, route):
            """Record one route and complete it immediately."""
            self.routes.append(route)
            self.on_state(RouteState.SUCCEEDED)
            return True

        def cancel(self):
            """Accept the controller lifecycle contract."""

        def wait(self, timeout=None):
            """Report that no worker remains."""
            return True

    navigator = Navigator()
    backend = BasicNavigatorBackend(navigator)
    spin_timeouts = []

    def publish_pose(node, timeout_sec):
        spin_timeouts.append(timeout_sec)
        if other_callback_first and len(spin_timeouts) == 1:
            return  # Another ready callback, including BasicNavigator's AMCL callback.
        message = PoseWithCovarianceStamped()
        message.header.frame_id = 'map'
        message.pose.pose.position.x = 2.0
        message.pose.pose.position.y = 2.0
        message.pose.pose.orientation.w = 1.0
        navigator.pose_callback(message)

    monkeypatch.setattr(nav2_backend.rclpy, 'ok', lambda: True)
    monkeypatch.setattr(nav2_backend.rclpy, 'spin_once', publish_pose)
    semantic, occupancy = runtime_map(tmp_path)
    runtime = RuntimeController(
        semantic, occupancy, backend, executor_factory=CapturingExecutor)
    runtime.process_text('Đi từ A đến B')
    assert executors[0].routes == [('b',)]
    assert spin_timeouts and 0 < spin_timeouts[0] <= 0.1


def test_missing_localization_reports_error_and_retry_dispatches(tmp_path):
    """An unavailable pose is distinct from a known outside-region pose."""
    runtime, backend, events = controller(tmp_path, pose=None)
    runtime.process_text('Đi đến B')
    assert events['error'][-1].code == 'localization_error'
    assert backend.calls == []
    runtime._current_pose = lambda: GoalPose(20.0, 20.0, 0.0)
    runtime.process_text('Đi đến B')
    assert runtime.wait(2)
    assert backend.calls == ['b']


def test_invalid_text_reports_typed_error_and_sends_no_goal(tmp_path):
    """Empty, unknown, and ambiguous destinations must not leak a Nav2 goal."""
    runtime, backend, events = controller(tmp_path)
    for text, code in (('', 'empty_transcript'),
                       ('Đi đến nơi không có', 'unknown_region'),
                       ('Đi đến A và B', 'ambiguous_destination')):
        runtime.process_text(text)
        error = events['error'][-1]
        assert isinstance(error, RuntimeErrorInfo)
        assert error.code == code
        assert runtime.state is RuntimeState.ERROR
    assert backend.calls == []
    assert events['route'] == []


def test_active_route_rejects_second_command_then_cancel_releases(tmp_path):
    """A second command cannot queue behind or replace an active route."""
    backend = Backend(block=True)
    runtime, _, events = controller(tmp_path, backend=backend)
    runtime.process_text('Đi đến A')
    assert backend.entered.wait(2)
    runtime.process_text('Đi đến B')
    assert events['error'][-1].code == 'route_active'
    assert backend.calls == ['a']
    runtime.cancel()
    assert runtime.wait(2)
    assert runtime.state is RuntimeState.CANCELED
    assert not runtime.is_busy


def test_adapter_and_nav2_failures_stay_typed_and_send_no_extra_goal(
        tmp_path):
    """External failures stay diagnosable instead of silently succeeding."""
    runtime, backend, events = controller(tmp_path)
    runtime.report_error('microphone_error', 'Không mở được microphone')
    runtime.report_error('model_error', 'Gemini API không khả dụng')
    assert [error.code for error in events['error'][-2:]] == [
        'microphone_error', 'model_error']
    assert backend.calls == []

    failing = Backend(outcome=RouteState.FAILED)
    runtime, _, events = controller(tmp_path, backend=failing)
    runtime.process_text('Đi đến B')
    assert runtime.wait(2)
    assert events['error'][-1].code == 'nav2_failed'
    assert runtime.state is RuntimeState.ERROR
    assert failing.calls == ['b']


def test_reentrant_listeners_close_admission_without_deadlock_or_late_route(
        tmp_path):
    """Public callbacks may close admission synchronously on their own thread."""
    runtime, backend, _ = controller(tmp_path)
    runtime.add_listener('transcript',
                         lambda transcript: runtime.close_admission())
    text_call = threading.Thread(
        target=runtime.process_text, args=('Đi đến B',), daemon=True)
    text_call.start()
    text_call.join(0.5)
    assert not text_call.is_alive(), 'transcript callback deadlocked admission'
    assert backend.calls == []

    runtime, backend, _ = controller(tmp_path)
    runtime.add_listener('error',
                         lambda error: runtime.close_admission())
    error_call = threading.Thread(
        target=runtime.report_error,
        args=('microphone_error', 'Không mở được microphone'), daemon=True)
    error_call.start()
    error_call.join(0.5)
    assert not error_call.is_alive(), 'error callback deadlocked admission'
    assert backend.calls == []
