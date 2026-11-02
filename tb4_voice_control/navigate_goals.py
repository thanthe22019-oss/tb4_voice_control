"""Navigate through named goals from a YAML file with Nav2."""

import argparse
from dataclasses import dataclass
import math
from pathlib import Path
import sys
import time

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from lifecycle_msgs.srv import GetState
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
import rclpy
from rclpy.utilities import remove_ros_args
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


def goal_to_pose(navigator, frame_id, goal):
    """Convert a planar goal to a stamped ROS pose."""
    pose = PoseStamped()
    pose.header.frame_id = frame_id
    pose.header.stamp = navigator.get_clock().now().to_msg()
    pose.pose.position.x = goal.x
    pose.pose.position.y = goal.y
    pose.pose.orientation.z = math.sin(goal.yaw / 2.0)
    pose.pose.orientation.w = math.cos(goal.yaw / 2.0)
    return pose


def wait_for_amcl_pose(navigator, timeout):
    """Wait for AMCL to provide a localized pose."""
    deadline = time.monotonic() + timeout
    navigator.info('Waiting for a real AMCL pose...')
    while rclpy.ok() and not navigator.initial_pose_received:
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return False
        rclpy.spin_once(navigator, timeout_sec=min(0.2, remaining))
    return navigator.initial_pose_received


def wait_for_active_node(navigator, node_name, timeout):
    """Wait until one Nav2 lifecycle node reaches active state."""
    client = navigator.create_client(GetState, f'{node_name}/get_state')
    deadline = time.monotonic() + timeout
    try:
        while rclpy.ok():
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return False
            if not client.wait_for_service(timeout_sec=min(0.5, remaining)):
                continue
            future = client.call_async(GetState.Request())
            rclpy.spin_until_future_complete(
                navigator,
                future,
                timeout_sec=min(1.0, remaining),
            )
            response = future.result() if future.done() else None
            if response is not None and response.current_state.label == 'active':
                return True
            time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))
        return False
    finally:
        navigator.destroy_client(client)


def wait_for_nav2(navigator, timeout):
    """Verify localization, lifecycle state and action availability."""
    start = time.monotonic()
    if not wait_for_amcl_pose(navigator, timeout):
        navigator.error(
            'No /amcl_pose received. Set 2D Pose Estimate in RViz first.'
        )
        return False

    remaining = timeout - (time.monotonic() - start)
    if remaining <= 0.0 or not wait_for_active_node(
        navigator, 'bt_navigator', remaining
    ):
        navigator.error('bt_navigator did not become active before timeout.')
        return False

    remaining = timeout - (time.monotonic() - start)
    if remaining <= 0.0 or not navigator.nav_to_pose_client.wait_for_server(
        timeout_sec=remaining
    ):
        navigator.error('/navigate_to_pose is not available before timeout.')
        return False
    navigator.info('AMCL and Nav2 are ready.')
    return True


def navigate_one_goal(navigator, frame_id, goal, timeout, feedback_period):
    """Execute one goal, canceling it when its deadline expires."""
    navigator.info(
        f'Starting {goal.name}: x={goal.x:.3f}, y={goal.y:.3f}, '
        f'yaw={goal.yaw:.3f} rad'
    )
    if not navigator.goToPose(goal_to_pose(navigator, frame_id, goal)):
        navigator.error(f'{goal.name} was rejected by Nav2.')
        return TaskResult.FAILED

    deadline = time.monotonic() + timeout
    next_feedback = time.monotonic() + feedback_period
    while rclpy.ok() and not navigator.isTaskComplete():
        now = time.monotonic()
        if now >= deadline:
            navigator.error(f'{goal.name} exceeded {timeout:.1f} seconds; canceling.')
            navigator.cancelTask()
            return TaskResult.CANCELED
        if now >= next_feedback:
            feedback = navigator.getFeedback()
            if feedback is not None:
                distance = feedback.distance_remaining
                navigator.info(
                    f'{goal.name} in progress; distance remaining: {distance:.2f} m'
                )
            next_feedback = now + feedback_period

    if not rclpy.ok():
        navigator.cancelTask()
        return TaskResult.CANCELED
    return navigator.getResult()


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
        navigator.info(
            f'Loaded {len(goals)} goal(s) from {arguments.goals_file}: '
            + ', '.join(goal.name for goal in goals)
        )
        if not wait_for_nav2(navigator, arguments.nav2_timeout):
            return 3

        for index, goal in enumerate(goals, start=1):
            navigator.info(f'Executing goal {index}/{len(goals)}.')
            active_task = True
            result = navigate_one_goal(
                navigator,
                frame_id,
                goal,
                arguments.goal_timeout,
                arguments.feedback_period,
            )
            active_task = False
            if result != TaskResult.SUCCEEDED:
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
