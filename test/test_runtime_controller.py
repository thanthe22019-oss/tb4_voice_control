"""Exercise the complete text-to-route runtime without ROS, Qt, or hardware."""

import threading

import numpy as np

from tb4_voice_control.command_parser import Intent
from tb4_voice_control.map_model import MapMetadata, OccupancyMap
from tb4_voice_control.regions import GoalPose, Region, SemanticMap
from tb4_voice_control.route_executor import RouteState
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


def controller(tmp_path, backend=None, pose=None):
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
    runtime.report_error('model_error', 'CUDA không khả dụng')
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
