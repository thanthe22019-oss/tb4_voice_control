"""Record a real AMCL pose as a named navigation goal in YAML."""

import argparse
import math
from pathlib import Path
import re
import sys
import tempfile
import time

from geometry_msgs.msg import PoseWithCovarianceStamped
import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.utilities import remove_ros_args
import yaml


GOAL_NAME_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9_-]*$')


def quaternion_to_yaw(x, y, z, w):
    """Return planar yaw from a quaternion."""
    sin_yaw = 2.0 * (w * z + x * y)
    cos_yaw = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(sin_yaw, cos_yaw)


def load_goal_file(path):
    """Load and validate the minimal goal-file structure."""
    if not path.exists():
        return {'frame_id': 'map', 'goals': {}}

    with path.open('r', encoding='utf-8') as stream:
        data = yaml.safe_load(stream) or {}

    if not isinstance(data, dict):
        raise ValueError('Goal YAML root must be a mapping')
    frame_id = data.get('frame_id', 'map')
    goals = data.get('goals', {})
    if not isinstance(frame_id, str) or not frame_id:
        raise ValueError('frame_id must be a non-empty string')
    if not isinstance(goals, dict):
        raise ValueError('goals must be a mapping')
    return {'frame_id': frame_id, 'goals': goals}


def save_goal_file(path, data):
    """Atomically save goal data next to its destination file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode='w',
        encoding='utf-8',
        dir=path.parent,
        prefix=f'.{path.name}.',
        suffix='.tmp',
        delete=False,
    ) as stream:
        yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)
        temporary_path = Path(stream.name)
    temporary_path.replace(path)


def parse_arguments():
    """Parse application arguments while allowing standard ROS arguments."""
    parser = argparse.ArgumentParser(
        description='Record one real /amcl_pose sample into a goal YAML file.'
    )
    parser.add_argument('--name', required=True, help='Goal name, for example goal_1')
    parser.add_argument('--output', required=True, help='Destination goals.yaml path')
    parser.add_argument(
        '--timeout',
        type=float,
        default=15.0,
        help='Seconds to wait for /amcl_pose (default: 15)',
    )
    arguments = parser.parse_args(remove_ros_args(args=sys.argv)[1:])
    if not GOAL_NAME_PATTERN.fullmatch(arguments.name):
        parser.error('--name must start with a letter and contain letters, digits, _ or -')
    if arguments.timeout <= 0.0:
        parser.error('--timeout must be greater than zero')
    return arguments


def main():
    """Wait for AMCL and record the received pose."""
    arguments = parse_arguments()
    rclpy.init(args=sys.argv)
    node = rclpy.create_node('tb4_voice_control_goal_recorder')
    received_pose = None

    qos = QoSProfile(depth=1)
    qos.reliability = ReliabilityPolicy.RELIABLE
    qos.durability = DurabilityPolicy.TRANSIENT_LOCAL

    def pose_callback(message):
        nonlocal received_pose
        if received_pose is None:
            received_pose = message

    subscription = node.create_subscription(
        PoseWithCovarianceStamped,
        '/amcl_pose',
        pose_callback,
        qos,
    )
    deadline = time.monotonic() + arguments.timeout
    node.get_logger().info('Waiting for one real pose on /amcl_pose...')

    try:
        while rclpy.ok() and received_pose is None and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)

        if received_pose is None:
            node.get_logger().error(
                'No /amcl_pose received. Set the initial pose and verify AMCL first.'
            )
            return 2

        frame_id = received_pose.header.frame_id or 'map'
        if frame_id != 'map':
            node.get_logger().error(
                f'Expected /amcl_pose in map frame, received {frame_id!r}'
            )
            return 3

        pose = received_pose.pose.pose
        goal = {
            'x': float(pose.position.x),
            'y': float(pose.position.y),
            'yaw': float(
                quaternion_to_yaw(
                    pose.orientation.x,
                    pose.orientation.y,
                    pose.orientation.z,
                    pose.orientation.w,
                )
            ),
        }
        output_path = Path(arguments.output).expanduser().resolve()
        data = load_goal_file(output_path)
        if data['frame_id'] != frame_id:
            node.get_logger().error(
                f'Goal file frame {data["frame_id"]!r} does not match {frame_id!r}'
            )
            return 4
        data['goals'][arguments.name] = goal
        save_goal_file(output_path, data)
        node.get_logger().info(
            f'Recorded {arguments.name}: x={goal["x"]:.3f}, '
            f'y={goal["y"]:.3f}, yaw={goal["yaw"]:.3f} rad -> {output_path}'
        )
        return 0
    except (OSError, ValueError, yaml.YAMLError) as error:
        node.get_logger().error(f'Could not update goal file: {error}')
        return 5
    finally:
        node.destroy_subscription(subscription)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
