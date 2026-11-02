"""Navigate through named goals from a YAML file with Nav2."""

import argparse
from dataclasses import dataclass
import math
from pathlib import Path
import sys
import threading

from ament_index_python.packages import get_package_share_directory
from nav2_simple_commander.robot_navigator import BasicNavigator
import rclpy
from rclpy.utilities import remove_ros_args
from tb4_voice_control.nav2_backend import BasicNavigatorBackend
from tb4_voice_control.nav2_backend import goal_to_pose  # noqa: F401
from tb4_voice_control.nav2_backend import navigate_one_goal  # noqa: F401
from tb4_voice_control.nav2_backend import wait_for_active_node  # noqa: F401
from tb4_voice_control.nav2_backend import wait_for_amcl_pose  # noqa: F401
from tb4_voice_control.nav2_backend import wait_for_nav2  # noqa: F401
from tb4_voice_control.route_executor import RouteState
import yaml


@dataclass(frozen=True)
class Goal:
    """One validated planar navigation goal."""

    name: str
    x: float
    y: float
    yaw: float


def default_goals_file():
    """Return the installed goals file."""
    share_directory = get_package_share_directory('tb4_voice_control')
    return Path(share_directory) / 'config' / 'goals.yaml'


def load_goals(path, selected_names=None):
    """Load ordered, finite planar goals from YAML."""
    with path.open('r', encoding='utf-8') as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict):
        raise ValueError('Goal YAML root must be a mapping')
    frame_id = data.get('frame_id')
    raw_goals = data.get('goals')
    if not isinstance(frame_id, str) or not frame_id.strip():
        raise ValueError('frame_id must be a non-empty string')
    if not isinstance(raw_goals, dict) or not raw_goals:
        raise ValueError('goals must be a non-empty mapping')

    names = list(raw_goals) if not selected_names else selected_names
    unknown_names = [name for name in names if name not in raw_goals]
    if unknown_names:
        raise ValueError(f'Unknown goal name(s): {", ".join(unknown_names)}')

    goals = []
    for name in names:
        values = raw_goals[name]
        if not isinstance(values, dict):
            raise ValueError(f'{name} must be a mapping')
        missing = [key for key in ('x', 'y', 'yaw') if key not in values]
        if missing:
            raise ValueError(f'{name} is missing: {", ".join(missing)}')
        try:
            x = float(values['x'])
            y = float(values['y'])
            yaw = float(values['yaw'])
        except (TypeError, ValueError) as error:
            raise ValueError(f'{name} x, y and yaw must be numbers') from error
        if not all(math.isfinite(value) for value in (x, y, yaw)):
            raise ValueError(f'{name} x, y and yaw must be finite')
        goals.append(Goal(name=name, x=x, y=y, yaw=yaw))
    return frame_id, goals


def parse_arguments():
    """Parse application arguments while preserving ROS arguments."""
    parser = argparse.ArgumentParser(
        description='Execute named navigation goals sequentially with Nav2.'
    )
    parser.add_argument(
        '--goals-file',
        type=Path,
        default=default_goals_file(),
        help='Goal YAML path (default: installed config/goals.yaml)',
    )
    parser.add_argument(
        '--goal',
        action='append',
        dest='goals',
        help='Goal name to execute; repeat to choose an order (default: all)',
    )
    parser.add_argument(
        '--nav2-timeout',
        type=float,
        default=60.0,
        help='Seconds to wait for AMCL and Nav2 (default: 60)',
    )
    parser.add_argument(
        '--goal-timeout',
        type=float,
        default=180.0,
        help='Maximum seconds for each goal (default: 180)',
    )
    parser.add_argument(
        '--feedback-period',
        type=float,
        default=5.0,
        help='Seconds between progress messages (default: 5)',
    )
    arguments = parser.parse_args(remove_ros_args(args=sys.argv)[1:])
    for option in ('nav2_timeout', 'goal_timeout', 'feedback_period'):
        if getattr(arguments, option) <= 0.0:
            parser.error(f'--{option.replace("_", "-")} must be greater than zero')
    return arguments


def main():
    """Load goals and execute them in YAML or requested order."""
    arguments = parse_arguments()
    try:
        frame_id, goals = load_goals(
            arguments.goals_file.expanduser().resolve(), arguments.goals
        )
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f'Invalid goal file: {error}', file=sys.stderr)
        return 2

    rclpy.init(args=sys.argv)
    navigator = BasicNavigator(node_name='tb4_voice_control_goal_navigator')
    active_task = False
    try:
        backend = BasicNavigatorBackend(
            navigator, frame_id=frame_id, nav2_timeout=arguments.nav2_timeout,
            goal_timeout=arguments.goal_timeout, feedback_period=arguments.feedback_period)
        navigator.info(
            f'Loaded {len(goals)} goal(s) from {arguments.goals_file}: '
            + ', '.join(goal.name for goal in goals)
        )
        if not backend.wait_until_ready():
            return 3

        for index, goal in enumerate(goals, start=1):
            navigator.info(f'Executing goal {index}/{len(goals)}.')
            active_task = True
            result = backend.execute(goal, threading.Event(), None)
            active_task = False
            if result is not RouteState.SUCCEEDED:
                navigator.error(f'{goal.name} finished with result {result.name}.')
                return 4
            navigator.info(f'{goal.name} succeeded.')

        navigator.info('All navigation goals succeeded.')
        return 0
    except KeyboardInterrupt:
        navigator.warn('Interrupted by user; canceling the active goal.')
        if active_task:
            navigator.cancelTask()
        return 130
    finally:
        navigator.destroyNode()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
