"""Tests for navigation goal file parsing and pose conversion."""

import math

import pytest
from tb4_voice_control.navigate_goals import Goal, goal_to_pose, load_goals
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
