"""Tests for navigation goal file parsing and pose conversion."""

import math
from types import SimpleNamespace

import pytest
from tb4_voice_control import navigate_goals
from tb4_voice_control.navigate_goals import Goal, goal_to_pose, load_goals
from tb4_voice_control.route_executor import RouteState
import yaml


class ClockStub:
    """Minimal clock used by the pose conversion test."""

    class NowStub:
        """Return a deterministic ROS timestamp message."""

        def to_msg(self):
            """Create the timestamp message."""
            from builtin_interfaces.msg import Time
            return Time(sec=12, nanosec=34)

    def now(self):
        """Return the deterministic clock sample."""
        return self.NowStub()


class NavigatorStub:
    """Minimal navigator used by the pose conversion test."""

    def get_clock(self):
        """Return a deterministic clock."""
        return ClockStub()


def test_load_goals_preserves_selected_order(tmp_path):
    """Selected goals are loaded in the explicitly requested order."""
    path = tmp_path / 'goals.yaml'
    path.write_text(yaml.safe_dump({
        'frame_id': 'map',
        'goals': {
            'first': {'x': 1, 'y': 2, 'yaw': 0.1},
            'second': {'x': 3, 'y': 4, 'yaw': -0.2},
        },
    }), encoding='utf-8')

    frame_id, goals = load_goals(path, ['second', 'first'])

    assert frame_id == 'map'
    assert [goal.name for goal in goals] == ['second', 'first']


@pytest.mark.parametrize(
    'document',
    [
        {'frame_id': 'map', 'goals': {}},
        {'frame_id': '', 'goals': {'a': {'x': 0, 'y': 0, 'yaw': 0}}},
        {'frame_id': 'map', 'goals': {'a': {'x': 0, 'y': 0}}},
        {'frame_id': 'map', 'goals': {'a': {'x': math.inf, 'y': 0, 'yaw': 0}}},
    ],
)
def test_load_goals_rejects_invalid_documents(tmp_path, document):
    """Malformed or unsafe goals are rejected before contacting Nav2."""
    path = tmp_path / 'goals.yaml'
    path.write_text(yaml.safe_dump(document), encoding='utf-8')

    with pytest.raises(ValueError):
        load_goals(path)


def test_goal_to_pose_converts_yaw():
    """Planar yaw is converted to a normalized quaternion."""
    goal = Goal(name='test', x=1.25, y=-2.5, yaw=math.pi / 2.0)

    pose = goal_to_pose(NavigatorStub(), 'map', goal)

    assert pose.header.frame_id == 'map'
    assert pose.header.stamp.sec == 12
    assert pose.pose.position.x == pytest.approx(1.25)
    assert pose.pose.position.y == pytest.approx(-2.5)
    assert pose.pose.orientation.z == pytest.approx(math.sqrt(0.5))
    assert pose.pose.orientation.w == pytest.approx(math.sqrt(0.5))


@pytest.mark.parametrize('ready, result, expected, goal_count, cancels', [
    (True, RouteState.SUCCEEDED, 0, 2, 0),
    (False, RouteState.SUCCEEDED, 3, 0, 0),
    (True, RouteState.FAILED, 4, 1, 0),
    (True, RouteState.CANCELED, 4, 1, 0),
    (True, KeyboardInterrupt, 130, 1, 1),
])
def test_cli_backend_preserves_exit_codes_and_stops_on_failure(
        tmp_path, monkeypatch, ready, result, expected, goal_count, cancels):
    """CLI readiness, failure, and Ctrl+C retain their established exit codes."""
    path = tmp_path / 'goals.yaml'
    path.write_text(yaml.safe_dump({
        'frame_id': 'map', 'goals': {
            'a': {'x': 1, 'y': 2, 'yaw': 0},
            'b': {'x': 3, 'y': 4, 'yaw': 0},
        }}), encoding='utf-8')
    arguments = SimpleNamespace(goals_file=path, goals=None, nav2_timeout=5,
                                goal_timeout=10, feedback_period=1)
    calls = []
    navigator = SimpleNamespace(
        info=lambda message: None, error=lambda message: None,
        warn=lambda message: None, cancelTask=lambda: calls.append('cancel'),
        destroyNode=lambda: calls.append('destroy'))

    class Backend:
        """Replace external navigation while retaining the real CLI control flow."""

        def __init__(self, actual_navigator, **options):
            assert actual_navigator is navigator
            assert options == {'frame_id': 'map', 'nav2_timeout': 5,
                               'goal_timeout': 10, 'feedback_period': 1}

        def wait_until_ready(self):
            return ready

        def execute(self, goal, cancel_event, on_progress):
            calls.append(goal.name)
            if result is KeyboardInterrupt:
                raise KeyboardInterrupt
            return result

    monkeypatch.setattr(navigate_goals, 'parse_arguments', lambda: arguments)
    monkeypatch.setattr(navigate_goals, 'BasicNavigator', lambda **options: navigator)
    monkeypatch.setattr(navigate_goals, 'BasicNavigatorBackend', Backend)
    monkeypatch.setattr(navigate_goals.rclpy, 'init', lambda **options: None)
    monkeypatch.setattr(navigate_goals.rclpy, 'ok', lambda: True)
    monkeypatch.setattr(navigate_goals.rclpy, 'shutdown', lambda: calls.append('shutdown'))

    assert navigate_goals.main() == expected
    assert sum(item in ('a', 'b') for item in calls) == goal_count
    assert calls.count('cancel') == cancels
    assert calls[-2:] == ['destroy', 'shutdown']


def test_cli_bad_goal_file_does_not_initialize_ros(tmp_path, monkeypatch):
    """Invalid goal files still exit 2 before touching ROS."""
    monkeypatch.setattr(navigate_goals, 'parse_arguments', lambda: SimpleNamespace(
        goals_file=tmp_path / 'missing.yaml', goals=None))

    def unexpected_init(**options):
        pytest.fail('Invalid input must not initialize ROS')

    monkeypatch.setattr(navigate_goals.rclpy, 'init', unexpected_init)
    assert navigate_goals.main() == 2
