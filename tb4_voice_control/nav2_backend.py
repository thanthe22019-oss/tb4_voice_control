"""ROS/Nav2 readiness, planar pose conversion, and blocking leg execution."""

from contextlib import contextmanager
from dataclasses import dataclass
import math
import threading
import time

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from tb4_voice_control.regions import GoalPose
from tb4_voice_control.route_executor import CleanupState, LegProgress, RouteState


def _stopped(cancel_event):
    return not rclpy.ok() or (cancel_event is not None and cancel_event.is_set())


@dataclass
class _ActionCleanup:
    send: object = None
    handle: object = None
    cancel: object = None
    result: object = None
    owned: bool = False


def goal_to_pose(navigator, frame_id, goal):
    """Convert a region or flat planar CLI goal to a stamped ROS pose."""
    coordinates = getattr(goal, 'goal', goal)
    pose = PoseStamped()
    pose.header.frame_id = frame_id
    pose.header.stamp = navigator.get_clock().now().to_msg()
    pose.pose.position.x = float(coordinates.x)
    pose.pose.position.y = float(coordinates.y)
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
                      cancel_event=None, on_progress=None, on_unresolved=None):
    """Execute a ready goal; cancel on deadline, shutdown, or cooperative request."""
    if hasattr(navigator.nav_to_pose_client, 'send_goal_async'):
        return _navigate_action(navigator, frame_id, goal, timeout, feedback_period,
                                cancel_event, on_progress, on_unresolved)
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


def _navigate_action(navigator, frame_id, goal, timeout, feedback_period,
                     cancel_event, on_progress, on_unresolved=None):
    """Own Humble action futures; unresolved cleanup is reported as failure."""
    deadline = time.monotonic() + timeout
    client = navigator.nav_to_pose_client
    while not _stopped(cancel_event):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            navigator.error('Action discovery timed out.')
            return TaskResult.FAILED
        if client.wait_for_server(timeout_sec=min(0.2, remaining)):
            break
    if _stopped(cancel_event):
        return TaskResult.CANCELED
    message = NavigateToPose.Goal()
    message.pose = goal_to_pose(navigator, frame_id, goal)
    action = _ActionCleanup()
    try:
        action.send = client.send_goal_async(message, navigator._feedbackCallback)
        return _finish_action(navigator, action, deadline, timeout, feedback_period,
                              goal, cancel_event, on_progress, on_unresolved)
    except Exception as error:
        if on_unresolved is None:
            raise
        if not action.owned:
            on_unresolved(action)
        navigator.error(f'Action transport failed; cleanup remains pending: {error}')
        return TaskResult.FAILED


def _finish_action(navigator, action, deadline, timeout, feedback_period,
                   goal, cancel_event, on_progress, on_unresolved):
    send = action.send

    def cancel_late(future):
        try:
            handle = future.result()
            if handle is not None and handle.accepted:
                handle.cancel_goal_async()
                navigator.error('Late accepted goal: cancellation requested; outcome unconfirmed.')
        except Exception as error:  # noqa: B902 - asynchronous transport boundary
            navigator.error(f'Late goal cleanup failed: {error}')

    while not send.done() and not _stopped(cancel_event):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        rclpy.spin_until_future_complete(navigator, send, timeout_sec=min(0.1, remaining))
    if not send.done() or _stopped(cancel_event):
        if on_unresolved is None:
            send.add_done_callback(cancel_late)
        else:
            on_unresolved(action)
        navigator.error('Goal acceptance unresolved; cancellation outcome is indeterminate.')
        return TaskResult.FAILED
    handle = send.result()
    action.handle = handle
    if handle is None or not handle.accepted:
        navigator.error('Goal was rejected by Nav2.')
        return TaskResult.FAILED
    result = handle.get_result_async()
    action.result = result
    next_feedback = time.monotonic() + feedback_period
    while not result.done() and not _stopped(cancel_event):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        rclpy.spin_until_future_complete(navigator, result, timeout_sec=min(0.1, remaining))
        now = time.monotonic()
        if now >= next_feedback:
            feedback = navigator.getFeedback()
            if feedback is not None and on_progress is not None:
                duration = feedback.navigation_time
                on_progress(LegProgress(getattr(goal, 'id', goal.name),
                                        distance_remaining=feedback.distance_remaining,
                                        elapsed_seconds=duration.sec + duration.nanosec / 1e9))
            next_feedback = now + feedback_period
    if result.done():
        status = result.result().status
        if status not in (GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_ABORTED,
                          GoalStatus.STATUS_CANCELED):
            if on_unresolved is not None:
                on_unresolved(action)
            return TaskResult.FAILED
        return {GoalStatus.STATUS_SUCCEEDED: TaskResult.SUCCEEDED,
                GoalStatus.STATUS_CANCELED: TaskResult.CANCELED}.get(status, TaskResult.FAILED)
    canceled_by_user = _stopped(cancel_event)
    cancel = handle.cancel_goal_async()
    action.cancel = cancel
    cleanup_deadline = time.monotonic() + min(timeout, 1.0)
    while not cancel.done() and rclpy.ok() and time.monotonic() < cleanup_deadline:
        rclpy.spin_until_future_complete(navigator, cancel, timeout_sec=0.1)
    if not cancel.done() or not cancel.result().goals_canceling:
        if on_unresolved is not None:
            on_unresolved(action)
        navigator.error('Goal cancellation rejected or unconfirmed.')
        return TaskResult.FAILED
    while not result.done() and rclpy.ok() and time.monotonic() < cleanup_deadline:
        rclpy.spin_until_future_complete(navigator, result, timeout_sec=0.1)
    if not result.done() or result.result().status != GoalStatus.STATUS_CANCELED:
        if on_unresolved is not None:
            on_unresolved(action)
        navigator.error('Goal cancellation terminal result is unconfirmed.')
        return TaskResult.FAILED
    return TaskResult.CANCELED if canceled_by_user else TaskResult.FAILED


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
        self._cleanup_state = CleanupState.QUIESCENT
        self._cleanup_force = threading.Event()
        self._cleanup_worker = None
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
            available = (not self._io_busy
                         and self._cleanup_state is CleanupState.QUIESCENT)
            if available:
                self._io_busy = True
        if available:
            try:
                deadline = time.monotonic() + timeout
                while rclpy.ok():
                    remaining = max(0.0, deadline - time.monotonic())
                    rclpy.spin_once(self.navigator, timeout_sec=remaining)
                    if self.current_pose is not None or remaining <= 0.0:
                        break
            finally:
                self._release_io()
        return self.current_pose

    def _release_io(self):
        with self._io_condition:
            self._io_busy = False
            self._io_condition.notify_all()

    @property
    def cleanup_state(self):
        """Return the state of unresolved action cleanup."""
        with self._io_condition:
            return self._cleanup_state

    def wait_for_cleanup(self, timeout=None):
        """Wait for cleanup to resolve or be explicitly abandoned."""
        with self._io_condition:
            self._io_condition.wait_for(
                lambda: self._cleanup_state is not CleanupState.PENDING, timeout)
            return self._cleanup_state

    def force_abort_cleanup(self):
        """Abandon local cleanup permanently after the operator requests it."""
        with self._io_condition:
            if self._cleanup_state is not CleanupState.PENDING:
                return False
            self._cleanup_force.set()
            worker = self._cleanup_worker
        if worker is not threading.current_thread():
            worker.join()
        return True

    def _start_cleanup(self, action):
        # The executing thread still owns I/O during this transfer.
        with self._io_condition:
            action.owned = True
            self._cleanup_state = CleanupState.PENDING
            self._cleanup_worker = threading.Thread(
                target=self._clean_action, args=(action,),
                name='nav2-cleanup', daemon=True)
            self._cleanup_worker.start()

    def _clean_action(self, action):
        confirmed = False
        with self._claim_io():
            while not self._cleanup_force.is_set():
                try:
                    if action.handle is None and action.send is not None and action.send.done():
                        action.handle = action.send.result()
                        if action.handle is None or not action.handle.accepted:
                            confirmed = True
                            break
                    if action.handle is not None and action.result is None:
                        action.result = action.handle.get_result_async()
                    cancel_acknowledged = False
                    if action.cancel is not None and action.cancel.done():
                        try:
                            cancel_acknowledged = bool(action.cancel.result().goals_canceling)
                        except Exception:
                            action.cancel = None
                    if action.result is not None and action.result.done():
                        status = action.result.result().status
                        if status in (GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_ABORTED):
                            confirmed = True
                            break
                        if status == GoalStatus.STATUS_CANCELED and cancel_acknowledged:
                            confirmed = True
                            break
                    if action.handle is not None and action.cancel is None:
                        try:
                            action.cancel = action.handle.cancel_goal_async()
                        except Exception:
                            pass
                    future = (action.send if action.handle is None else
                              action.cancel if action.cancel is not None and
                              not action.cancel.done() else action.result)
                    if rclpy.ok() and future is not None:
                        rclpy.spin_until_future_complete(
                            self.navigator, future, timeout_sec=0.1)
                        if future.done():
                            self._cleanup_force.wait(0.01)
                    else:
                        self._cleanup_force.wait(0.1)
                except Exception:
                    # Retry transient transport failures without surrendering ownership.
                    self._cleanup_force.wait(0.1)
        with self._io_condition:
            self._cleanup_state = (CleanupState.FORCE_ABORTED if self._cleanup_force.is_set()
                                   else CleanupState.QUIESCENT if confirmed
                                   else CleanupState.PENDING)
            self._io_condition.notify_all()

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
        if self.cleanup_state is not CleanupState.QUIESCENT:
            return False
        with self._claim_io():
            if self.cleanup_state is not CleanupState.QUIESCENT:
                return False
            return wait_for_nav2(self.navigator, self.nav2_timeout, cancel_event)

    def execute(self, region, cancel_event, on_progress) -> RouteState:
        """Run one region only after all readiness dependencies are available."""
        if self.cleanup_state is not CleanupState.QUIESCENT:
            return RouteState.FAILED
        with self._claim_io():
            if self.cleanup_state is not CleanupState.QUIESCENT:
                return RouteState.FAILED
            if not wait_for_nav2(self.navigator, self.nav2_timeout, cancel_event):
                return (RouteState.CANCELED if _stopped(cancel_event)
                        else RouteState.FAILED)
            result = navigate_one_goal(
                self.navigator, self.frame_id, region, self.goal_timeout,
                self.feedback_period, cancel_event, on_progress, self._start_cleanup)
        return {TaskResult.SUCCEEDED: RouteState.SUCCEEDED,
                TaskResult.CANCELED: RouteState.CANCELED}.get(result, RouteState.FAILED)
