"""ROS/Nav2 readiness, planar pose conversion, and blocking leg execution."""

from contextlib import contextmanager
import math
import threading
import time

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from lifecycle_msgs.srv import GetState
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from tb4_voice_control.regions import GoalPose
from tb4_voice_control.route_executor import LegProgress, RouteState


def _stopped(cancel_event):
    return not rclpy.ok() or (cancel_event is not None and cancel_event.is_set())


def goal_to_pose(navigator, frame_id, goal):
    """Convert a region or flat planar CLI goal to a stamped ROS pose."""
    coordinates = getattr(goal, 'goal', goal)
    pose = PoseStamped()
    pose.header.frame_id = frame_id
    pose.header.stamp = navigator.get_clock().now().to_msg()
    pose.pose.position.x = coordinates.x
    pose.pose.position.y = coordinates.y
    pose.pose.orientation.z = math.sin(coordinates.yaw / 2.0)
    pose.pose.orientation.w = math.cos(coordinates.yaw / 2.0)
    return pose


def wait_for_amcl_pose(navigator, timeout, cancel_event=None):
    """Wait for real localization while observing cancellation and shutdown."""
    deadline = time.monotonic() + timeout
    navigator.info('Waiting for a real AMCL pose...')
    while not _stopped(cancel_event) and not navigator.initial_pose_received:
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return False
        rclpy.spin_once(navigator, timeout_sec=min(0.2, remaining))
    return not _stopped(cancel_event) and navigator.initial_pose_received


def wait_for_active_node(navigator, node_name, timeout, cancel_event=None):
    """Wait until one Nav2 lifecycle node reaches active state."""
    client = navigator.create_client(GetState, f'{node_name}/get_state')
    deadline = time.monotonic() + timeout
    try:
        while not _stopped(cancel_event):
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return False
            if not client.wait_for_service(timeout_sec=min(0.2, remaining)):
                continue
            if _stopped(cancel_event):
                return False
            future = client.call_async(GetState.Request())
            rclpy.spin_until_future_complete(
                navigator, future, timeout_sec=min(0.2, remaining))
            response = future.result() if future.done() else None
            if response is not None and response.current_state.label == 'active':
                return not _stopped(cancel_event)
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
        return False
    finally:
        navigator.destroy_client(client)


def wait_for_nav2(navigator, timeout, cancel_event=None):
    """Verify AMCL, lifecycle activation, and action discovery before any goal."""
    deadline = time.monotonic() + timeout
    if not wait_for_amcl_pose(navigator, timeout, cancel_event):
        navigator.error('No /amcl_pose received. Set 2D Pose Estimate in RViz first.')
        return False
    remaining = deadline - time.monotonic()
    if remaining <= 0.0 or not wait_for_active_node(
            navigator, 'bt_navigator', remaining, cancel_event):
        navigator.error('bt_navigator did not become active before timeout.')
        return False
    while not _stopped(cancel_event):
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            break
        if navigator.nav_to_pose_client.wait_for_server(timeout_sec=min(0.2, remaining)):
            navigator.info('AMCL and Nav2 are ready.')
            return not _stopped(cancel_event)
    navigator.error('/navigate_to_pose is not available before timeout.')
    return False


def navigate_one_goal(navigator, frame_id, goal, timeout, feedback_period,
                      cancel_event=None, on_progress=None):
    """Execute a ready goal; cancel on deadline, shutdown, or cooperative request."""
    if _stopped(cancel_event):
        return TaskResult.CANCELED
    coordinates = getattr(goal, 'goal', goal)
    navigator.info(f'Starting {goal.name}: x={coordinates.x:.3f}, '
                   f'y={coordinates.y:.3f}, yaw={coordinates.yaw:.3f} rad')
    if not navigator.goToPose(goal_to_pose(navigator, frame_id, goal)):
        navigator.error(f'{goal.name} was rejected by Nav2.')
        return TaskResult.FAILED
    deadline = time.monotonic() + timeout
    next_feedback = time.monotonic() + feedback_period
    try:
        while not _stopped(cancel_event) and not navigator.isTaskComplete():
            now = time.monotonic()
            if now >= deadline:
                navigator.error(f'{goal.name} exceeded {timeout:.1f} seconds; canceling.')
                navigator.cancelTask()
                return TaskResult.FAILED
            if now >= next_feedback:
                feedback = navigator.getFeedback()
                if feedback is not None:
                    distance = feedback.distance_remaining
                    navigator.info(f'{goal.name} in progress; '
                                   f'distance remaining: {distance:.2f} m')
                    if on_progress is not None:
                        duration = feedback.navigation_time
                        on_progress(LegProgress(
                            getattr(goal, 'id', goal.name), distance_remaining=distance,
                            elapsed_seconds=duration.sec + duration.nanosec / 1e9))
                next_feedback = now + feedback_period
        if _stopped(cancel_event):
            navigator.cancelTask()
            return TaskResult.CANCELED
        return navigator.getResult()
    except Exception:
        navigator.cancelTask()
        raise


class BasicNavigatorBackend:
    """
    Adapt one BasicNavigator to the pure executor and AMCL pose observers.

    The caller initializes/shuts down rclpy and destroys the navigator after
    its route worker has joined. Pose callbacks run on the thread spinning ROS.
    """

    def __init__(self, navigator=None, *, frame_id='map', nav2_timeout=60.0,
                 goal_timeout=180.0, feedback_period=5.0, on_pose=None):
        """Use an injected navigator or construct one in an initialized ROS context."""
        if any(not math.isfinite(value) or value <= 0 for value in
               (nav2_timeout, goal_timeout, feedback_period)):
            raise ValueError('Navigation timeouts and feedback period must be positive and finite')
        self.navigator = navigator if navigator is not None else BasicNavigator(
            node_name='tb4_voice_control_route_navigator')
        self.frame_id = frame_id
        self.nav2_timeout = nav2_timeout
        self.goal_timeout = goal_timeout
        self.feedback_period = feedback_period
        self._on_pose = on_pose
        self._pose = None
        self._pose_lock = threading.Lock()
        self._io_lock = threading.Lock()
        self._io_condition = threading.Condition(self._io_lock)
        self._io_busy = False
        self._pose_subscription = self.navigator.create_subscription(
            PoseWithCovarianceStamped, 'amcl_pose', self._receive_pose,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                       reliability=ReliabilityPolicy.RELIABLE))

    @property
    def current_pose(self) -> GoalPose | None:
        """Read the latest real AMCL planar pose without spinning ROS."""
        with self._pose_lock:
            return self._pose

    def _receive_pose(self, message):
        if message.header.frame_id != self.frame_id:
            return
        pose = message.pose.pose
        q = pose.orientation
        current = GoalPose(pose.position.x, pose.position.y,
                           math.atan2(2 * (q.w * q.z + q.x * q.y),
                                      1 - 2 * (q.y * q.y + q.z * q.z)))
        with self._pose_lock:
            self._pose = current
        if self._on_pose is not None:
            self._on_pose(current)

    def poll_pose(self, timeout=0.0) -> GoalPose | None:
        """Spin idle localization without competing with a running navigation leg."""
        with self._io_condition:
            available = not self._io_busy
            if available:
                self._io_busy = True
        if available:
            try:
                if rclpy.ok():
                    rclpy.spin_once(self.navigator, timeout_sec=timeout)
            finally:
                self._release_io()
        return self.current_pose

    def _release_io(self):
        with self._io_condition:
            self._io_busy = False
            self._io_condition.notify()

    @contextmanager
    def _claim_io(self):
        with self._io_condition:
            while self._io_busy:
                self._io_condition.wait()
            self._io_busy = True
        try:
            yield
        finally:
            self._release_io()

    def wait_until_ready(self, cancel_event=None) -> bool:
        """Expose the same readiness gate to the CLI before its first leg."""
        with self._claim_io():
            return wait_for_nav2(self.navigator, self.nav2_timeout, cancel_event)

    def execute(self, region, cancel_event, on_progress) -> RouteState:
        """Run one region only after all readiness dependencies are available."""
        with self._claim_io():
            if not wait_for_nav2(self.navigator, self.nav2_timeout, cancel_event):
                return (RouteState.CANCELED if _stopped(cancel_event)
                        else RouteState.FAILED)
            result = navigate_one_goal(
                self.navigator, self.frame_id, region, self.goal_timeout,
                self.feedback_period, cancel_event, on_progress)
        return {TaskResult.SUCCEEDED: RouteState.SUCCEEDED,
                TaskResult.CANCELED: RouteState.CANCELED}.get(result, RouteState.FAILED)
