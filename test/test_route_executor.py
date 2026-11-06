"""Exercise route ordering and cancellation without ROS or Qt."""

import subprocess
import sys
import threading

import pytest

from tb4_voice_control.regions import GoalPose, Region
from tb4_voice_control.route_executor import CleanupState, LegProgress, RouteExecutor, RouteState


def regions():
    """Return two deliberately distinct route destinations."""
    return tuple(Region(name, name, (), (1, 2, 3), ((0, 0), (1, 0), (0, 1)),
                        GoalPose(x, 2.0, 0.0))
                 for name, x in [('a', 1.0), ('b', 3.0)])


class Backend:
    """Record real executor requests and optionally block until canceled."""

    def __init__(self, outcome=RouteState.SUCCEEDED, block=False):
        """Set the next leg outcome and synchronization events."""
        self.outcome = outcome
        self.block = block
        self.entered = threading.Event()
        self.calls = []

    def execute(self, region, cancel_event, on_progress):
        """Publish progress and wait cooperatively when requested."""
        self.calls.append(region.id)
        self.entered.set()
        on_progress(LegProgress(region.id, distance_remaining=1.25))
        if self.block:
            assert cancel_event.wait(2)
            return RouteState.CANCELED
        return self.outcome


def test_ordered_execution_publishes_leg_numbers_and_allows_restart():
    """Reversing or skipping legs must change the observed route and progress."""
    backend = Backend()
    states, progress = [], []
    executor = RouteExecutor(backend, regions(), on_state=states.append,
                             on_progress=progress.append)
    assert executor.state is RouteState.IDLE
    assert executor.start(('b', 'a'))
    assert executor.wait(2)
    assert backend.calls == ['b', 'a']
    assert states == [RouteState.RUNNING, RouteState.SUCCEEDED]
    assert [(item.region_id, item.leg_index, item.leg_count)
            for item in progress] == [('b', 1, 2), ('b', 1, 2),
                                      ('a', 2, 2), ('a', 2, 2)]
    assert progress[1].distance_remaining == 1.25
    assert executor.start(('a',))
    assert executor.wait(2)
    assert backend.calls == ['b', 'a', 'a']


@pytest.mark.parametrize('failure', ['rejected', 'timed out'])
def test_failure_stops_at_first_leg_and_allows_later_command(failure):
    """A failed backend leg must never dispatch the next destination."""
    backend = Backend(RouteState.FAILED)
    executor = RouteExecutor(backend, regions())
    assert executor.start(('a', 'b')), failure
    assert executor.wait(2)
    assert executor.state is RouteState.FAILED
    assert backend.calls == ['a']
    backend.outcome = RouteState.SUCCEEDED
    assert executor.start(('b',))
    assert executor.wait(2)
    assert executor.state is RouteState.SUCCEEDED


def test_cancel_rejects_concurrent_start_then_allows_restart():
    """Cancellation stays RUNNING until backend cleanup finishes."""
    backend = Backend(block=True)
    executor = RouteExecutor(backend, regions())
    executor.cancel()
    assert executor.start(('a', 'b'))
    assert backend.entered.wait(2)
    assert not executor.start(('b',))
    assert not executor.wait(0.001)
    executor.cancel()
    assert executor.wait(2)
    assert executor.state is RouteState.CANCELED
    assert backend.calls == ['a']
    backend.block = False
    assert executor.start(('b',))
    assert executor.wait(2)
    assert executor.state is RouteState.SUCCEEDED


def test_failed_cancel_confirmation_remains_failure():
    """A cancellation request cannot mask an unconfirmed backend failure."""
    class Unconfirmed(Backend):

        def execute(self, region, cancel_event, on_progress):
            self.entered.set()
            assert cancel_event.wait(2)
            return RouteState.FAILED

    backend = Unconfirmed()
    executor = RouteExecutor(backend, regions())
    assert executor.start(('a',))
    assert backend.entered.wait(2)
    executor.cancel()
    assert executor.wait(2)
    assert executor.state is RouteState.FAILED


def test_empty_route_succeeds_without_dispatch():
    """An already satisfied command must send no navigation goal."""
    backend = Backend()
    executor = RouteExecutor(backend, regions())
    assert executor.start(())
    assert executor.wait(2)
    assert executor.state is RouteState.SUCCEEDED
    assert backend.calls == []


def test_callback_can_cancel_before_first_goal_without_deadlock():
    """A controller callback can safely reenter the executor's public methods."""
    backend = Backend()
    executor = RouteExecutor(backend, regions(),
                             on_state=lambda state: executor.cancel())
    assert executor.start(('a', 'b'))
    assert executor.wait(2)
    assert executor.state is RouteState.CANCELED
    assert backend.calls == []


def test_only_one_simultaneous_start_is_accepted():
    """The admission lock prevents two workers from sharing a navigator."""
    backend = Backend(block=True)
    executor = RouteExecutor(backend, regions())
    barrier = threading.Barrier(8)
    accepted = []

    def start():
        barrier.wait()
        accepted.append(executor.start(('a',)))

    callers = [threading.Thread(target=start) for _ in range(8)]
    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join(2)
    assert accepted.count(True) == 1
    executor.cancel()
    assert executor.wait(2)
    assert len(backend.calls) <= 1


def test_backend_exception_becomes_failure_and_does_not_wedge_admission():
    """Unexpected ROS errors must stop the route and release RUNNING state."""
    backend = Backend()

    def fail(*args):
        raise RuntimeError('transport failed')

    backend.execute = fail
    executor = RouteExecutor(backend, regions())
    assert executor.start(('a', 'b'))
    assert executor.wait(2)
    assert executor.state is RouteState.FAILED
    assert executor.start(())
    assert executor.wait(2)


def test_unknown_region_is_rejected_without_changing_state():
    """Bad IDs cannot leave a worker stuck RUNNING or partially dispatch a route."""
    backend = Backend()
    executor = RouteExecutor(backend, regions())
    with pytest.raises(ValueError, match='missing'):
        executor.start(('a', 'missing'))
    assert executor.state is RouteState.IDLE
    assert backend.calls == []


def test_executor_import_has_no_ros_or_qt_dependency():
    """The pure executor must remain importable in a non-ROS process."""
    result = subprocess.run([sys.executable, '-c',
                             'import sys; import tb4_voice_control.route_executor; '
                             'assert not any(name.startswith(("rclpy", "PyQt", '
                             '"geometry_msgs", "nav2_")) for name in sys.modules)'],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


class CleanupBackend(Backend):
    """Hold an unresolved transport until the test confirms or aborts it."""

    def __init__(self):
        super().__init__(RouteState.FAILED)
        self.condition = threading.Condition()
        self.cleanup_state = CleanupState.QUIESCENT

    def execute(self, region, cancel_event, on_progress):
        with self.condition:
            self.cleanup_state = CleanupState.PENDING
        return super().execute(region, cancel_event, on_progress)

    def wait_for_cleanup(self, timeout=None):
        with self.condition:
            self.condition.wait_for(lambda: self.cleanup_state is not CleanupState.PENDING,
                                    timeout)
            return self.cleanup_state

    def finish(self, state):
        with self.condition:
            self.cleanup_state = state
            self.condition.notify_all()

    def force_abort_cleanup(self):
        self.finish(CleanupState.FORCE_ABORTED)
        return True


def test_cleanup_pending_keeps_executor_cleaning_and_rejects_second_route():
    """A failed route cannot release admission before cleanup confirms terminal state."""
    backend = CleanupBackend()
    cleaning = threading.Event()
    states = []

    def observe(state):
        states.append(state)
        if state.name == 'CLEANING':
            cleaning.set()

    executor = RouteExecutor(backend, regions(), on_state=observe)
    assert executor.start(('a',))
    try:
        assert cleaning.wait(1)
        assert executor.cleanup_state is CleanupState.PENDING
        assert not executor.start(('b',))
        assert not executor.wait(0.01)
        assert backend.calls == ['a']
    finally:
        backend.finish(CleanupState.QUIESCENT)
        executor.wait(1)
    assert [state.name for state in states] == ['RUNNING', 'CLEANING', 'FAILED']


def test_confirmed_cleanup_finishes_failed_route_and_allows_retry():
    backend = CleanupBackend()
    cleaning = threading.Event()
    executor = RouteExecutor(backend, regions(), on_state=lambda state:
                             cleaning.set() if state.name == 'CLEANING' else None)
    assert executor.start(('a',))
    assert cleaning.wait(1)
    assert not executor.wait(0.01)
    backend.finish(CleanupState.QUIESCENT)
    assert executor.wait(1)
    assert executor.state is RouteState.FAILED
    backend.entered.clear()
    assert executor.start(('b',))
    assert backend.entered.wait(1)
    backend.finish(CleanupState.QUIESCENT)
    assert executor.wait(1)


def test_force_abort_finishes_wait_but_never_restores_route_admission():
    backend = CleanupBackend()
    executor = RouteExecutor(backend, regions())
    assert executor.start(('a',))
    assert backend.entered.wait(1)
    assert executor.force_abort_cleanup()
    assert executor.wait(1)
    assert executor.state is RouteState.FAILED
    assert executor.cleanup_state is CleanupState.FORCE_ABORTED
    assert not executor.start(('b',))
    assert backend.calls == ['a']
