"""Check the real Nav2 adapter against deterministic external ROS boundaries."""

import math
import threading
from types import SimpleNamespace

from action_msgs.msg import GoalStatus
from builtin_interfaces.msg import Time
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import TaskResult
import pytest

from tb4_voice_control import nav2_backend
from tb4_voice_control.nav2_backend import BasicNavigatorBackend
from tb4_voice_control.regions import GoalPose, Region
from tb4_voice_control.route_executor import RouteState


class Navigator:
    """Represent only the BasicNavigator operations used by the adapter."""

    def __init__(self):
        """Set external dependencies healthy and configure one successful goal."""
        self.initial_pose_received = True
        self.active = True
        self.available = True
        self.accepted = True
        self.complete = True
        self.result = TaskResult.SUCCEEDED
        self.sent = []
        self.cancels = 0
        self.services = []
        self.destroyed_clients = []
        self.nav_to_pose_client = SimpleNamespace(wait_for_server=self.wait_for_server)

    def wait_for_server(self, timeout_sec):
        """Return the configured action discovery result."""
        return self.available

    def create_client(self, service, name):
        """Expose active lifecycle state through a completed ROS future."""
        self.services.append(name)
        response = SimpleNamespace(current_state=SimpleNamespace(
            label='active' if self.active else 'inactive'))
        future = SimpleNamespace(done=lambda: True, result=lambda: response)
        return SimpleNamespace(wait_for_service=lambda timeout_sec: True,
                               call_async=lambda request: future)

    def destroy_client(self, client):
        """Record lifecycle client cleanup."""
        self.destroyed_clients.append(client)

    def create_subscription(self, message, topic, callback, qos):
        """Capture the adapter's actual AMCL pose callback."""
        assert topic == 'amcl_pose'
        self.pose_callback = callback
        return object()

    def get_clock(self):
        """Return deterministic timestamps for outgoing goals."""
        return SimpleNamespace(now=lambda: SimpleNamespace(
            to_msg=lambda: Time(sec=12, nanosec=34)))

    def goToPose(self, pose):
        """Record the outgoing goal and emulate action acceptance."""
        self.sent.append(pose)
        return self.accepted

    def isTaskComplete(self):
        """Return configured completion state."""
        return self.complete

    def getFeedback(self):
        """Mirror NavigateToPose feedback's relevant ROS message fields."""
        return SimpleNamespace(distance_remaining=2.5,
                               navigation_time=SimpleNamespace(sec=3, nanosec=500000000),
                               current_pose=None)

    def getResult(self):
        """Return the configured ROS task result."""
        return self.result

    def cancelTask(self):
        """Record action cancellation."""
        self.cancels += 1

    def info(self, message):
        """Accept ROS diagnostic output."""

    error = info


@pytest.fixture
def ros(monkeypatch):
    """Advance deadlines deterministically without a ROS graph or real waits."""
    samples = iter(index * 0.05 for index in range(10000))
    monkeypatch.setattr(nav2_backend.time, 'monotonic', lambda: next(samples))
    monkeypatch.setattr(nav2_backend.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(nav2_backend.rclpy, 'ok', lambda: True)
    monkeypatch.setattr(nav2_backend.rclpy, 'spin_once', lambda *args, **kwargs: None)
    monkeypatch.setattr(nav2_backend.rclpy, 'spin_until_future_complete',
                        lambda *args, **kwargs: None)


def region():
    """Use a goal whose half-angle quaternion is easy to check independently."""
    return Region('b', 'Bay', (), (1, 2, 3), ((0, 0), (1, 0), (0, 1)),
                  GoalPose(1.25, -2.5, math.pi / 2))


def test_integer_yaml_goal_converts_to_real_ros_pose(tmp_path):
    """Accepted integer YAML coordinates satisfy actual ROS float setters."""
    from tb4_voice_control.regions import load_regions
    import yaml

    path = tmp_path / 'regions.yaml'
    path.write_text(yaml.safe_dump({
        'schema_version': 1, 'map': {'yaml': 'map.yaml', 'frame_id': 'map'},
        'regions': [{'id': 'a', 'name': 'A', 'aliases': [], 'color': [1, 2, 3],
                     'polygon_pixels': [[0, 0], [3, 0], [0, 3]],
                     'goal': {'x': 2, 'y': 1, 'yaw': 0}}],
    }), encoding='utf-8')
    goal = load_regions(path).regions[0]
    pose = nav2_backend.goal_to_pose(Navigator(), 'map', goal)
    assert (pose.pose.position.x, pose.pose.position.y) == (2.0, 1.0)


def test_region_maps_to_stamped_map_goal_and_readiness_checks(ros):
    """Correct readiness and quaternion conversion must precede dispatch."""
    navigator = Navigator()
    backend = BasicNavigatorBackend(navigator, nav2_timeout=2)
    assert backend.execute(region(), threading.Event(), lambda progress: None) \
        is RouteState.SUCCEEDED
    assert navigator.services == ['bt_navigator/get_state']
    assert len(navigator.destroyed_clients) == 1
    pose, = navigator.sent
    assert pose.header.frame_id == 'map'
    assert pose.header.stamp.sec == 12
    assert (pose.pose.position.x, pose.pose.position.y) == (1.25, -2.5)
    assert pose.pose.orientation.z == pytest.approx(math.sqrt(0.5))
    assert pose.pose.orientation.w == pytest.approx(math.sqrt(0.5))


@pytest.mark.parametrize('dependency', ['initial_pose_received', 'active', 'available'])
def test_unavailable_dependency_never_sends_a_goal(ros, dependency):
    """Missing AMCL, lifecycle activation, or action server gates dispatch."""
    navigator = Navigator()
    setattr(navigator, dependency, False)
    backend = BasicNavigatorBackend(navigator, nav2_timeout=0.6)
    assert backend.execute(region(), threading.Event(), lambda progress: None) \
        is RouteState.FAILED
    assert navigator.sent == []


def test_feedback_maps_distance_and_elapsed_time_then_timeout_cancels(ros):
    """Feedback must reach consumers and a deadline must cancel the ROS goal."""
    navigator = Navigator()
    navigator.complete = False
    backend = BasicNavigatorBackend(navigator, goal_timeout=0.8, feedback_period=0.01)
    progress = []
    assert backend.execute(region(), threading.Event(), progress.append) \
        is RouteState.FAILED
    assert navigator.cancels == 1
    assert progress
    assert progress[0].region_id == 'b'
    assert progress[0].distance_remaining == 2.5
    assert progress[0].elapsed_seconds == 3.5


def test_callbacks_run_without_backend_lock_held(ros):
    """Consumers can inspect backend state without inheriting its I/O lock."""
    navigator = Navigator()
    navigator.complete = False
    observed = []
    backend = BasicNavigatorBackend(navigator, goal_timeout=0.8, feedback_period=0.01,
                                    on_pose=lambda pose: observed.append(
                                        backend._io_lock.locked()))
    message = PoseWithCovarianceStamped()
    message.header.frame_id = 'map'

    def feedback():
        navigator.pose_callback(message)
        return SimpleNamespace(distance_remaining=1.0,
                               navigation_time=SimpleNamespace(sec=0, nanosec=0))

    navigator.getFeedback = feedback
    backend.execute(region(), threading.Event(),
                    lambda progress: observed.append(backend._io_lock.locked()))
    assert observed and not any(observed)


@pytest.mark.parametrize('result, expected', [
    (TaskResult.SUCCEEDED, RouteState.SUCCEEDED),
    (TaskResult.CANCELED, RouteState.CANCELED),
    (TaskResult.FAILED, RouteState.FAILED),
    (TaskResult.UNKNOWN, RouteState.FAILED),
])
def test_ros_result_maps_to_pure_state(ros, result, expected):
    """Unknown or failed ROS results cannot become successful route legs."""
    navigator = Navigator()
    navigator.result = result
    backend = BasicNavigatorBackend(navigator)
    assert backend.execute(region(), threading.Event(), lambda progress: None) is expected


def test_rejected_goal_is_failure_and_does_not_cancel_unaccepted_task(ros):
    """A rejected Nav2 request cannot advance a route."""
    navigator = Navigator()
    navigator.accepted = False
    backend = BasicNavigatorBackend(navigator)
    assert backend.execute(region(), threading.Event(), lambda progress: None) \
        is RouteState.FAILED
    assert navigator.cancels == 0


def test_cancellation_during_feedback_cancels_active_ros_goal(ros):
    """The worker handles cancellation on its next poll, without a second ROS thread."""
    navigator = Navigator()
    navigator.complete = False
    backend = BasicNavigatorBackend(navigator, feedback_period=0.01)
    canceled = threading.Event()
    assert backend.execute(region(), canceled, lambda progress: canceled.set()) \
        is RouteState.CANCELED
    assert navigator.cancels == 1


def test_precanceled_or_canceled_readiness_never_dispatches(ros, monkeypatch):
    """Cancellation before or during localization cannot leak a navigation request."""
    navigator = Navigator()
    backend = BasicNavigatorBackend(navigator)
    canceled = threading.Event()
    canceled.set()
    assert backend.execute(region(), canceled, lambda progress: None) is RouteState.CANCELED
    canceled.clear()
    navigator.initial_pose_received = False
    monkeypatch.setattr(nav2_backend.rclpy, 'spin_once',
                        lambda *args, **kwargs: canceled.set())
    assert backend.execute(region(), canceled, lambda progress: None) is RouteState.CANCELED
    assert navigator.sent == []


def test_amcl_updates_current_pose_and_callback_in_map_frame(ros):
    """Live localization must report ROS coordinates and yaw to the controller."""
    navigator = Navigator()
    poses = []
    backend = BasicNavigatorBackend(navigator, on_pose=poses.append)
    message = PoseWithCovarianceStamped()
    message.header.frame_id = 'map'
    message.pose.pose.position.x = 4.5
    message.pose.pose.position.y = -1.5
    message.pose.pose.orientation.z = math.sqrt(0.5)
    message.pose.pose.orientation.w = math.sqrt(0.5)
    navigator.pose_callback(message)
    assert backend.current_pose == GoalPose(4.5, -1.5, pytest.approx(math.pi / 2))
    assert poses == [backend.current_pose]
    message.header.frame_id = 'odom'
    navigator.pose_callback(message)
    assert len(poses) == 1
    assert backend.poll_pose() == backend.current_pose


class Future:
    """Small future matching rclpy's done, result and callback interface."""

    def __init__(self, value=None, done=False):
        self.value, self.ready, self.callbacks = value, done, []

    def done(self):
        return self.ready

    def result(self):
        return self.value

    def add_done_callback(self, callback):
        self.callbacks.append(callback)
        if self.ready:
            callback(self)

    def resolve(self, value):
        self.value, self.ready = value, True
        for callback in self.callbacks:
            callback(self)


def test_pending_send_times_out_and_late_acceptance_requests_cancel(ros):
    navigator = Navigator()
    pending = Future()
    navigator.nav_to_pose_client.send_goal_async = lambda *args: pending
    navigator._feedbackCallback = lambda message: None
    assert nav2_backend.navigate_one_goal(navigator, 'map', region(), 0.3, 1) \
        is TaskResult.FAILED
    cancels = []
    handle = SimpleNamespace(accepted=True, cancel_goal_async=lambda: cancels.append(True))
    pending.resolve(handle)
    assert cancels == [True]


def test_action_future_success_uses_real_message_and_terminal_status(ros):
    navigator = Navigator()
    result = Future(SimpleNamespace(status=GoalStatus.STATUS_SUCCEEDED), done=True)
    handle = SimpleNamespace(accepted=True, get_result_async=lambda: result)
    sent = []
    navigator.nav_to_pose_client.send_goal_async = lambda message, callback: (
        sent.append(message) or Future(handle, done=True))
    navigator._feedbackCallback = lambda message: None
    assert nav2_backend.navigate_one_goal(navigator, 'map', region(), 1, 1) \
        is TaskResult.SUCCEEDED
    assert sent[0].pose.pose.position.x == 1.25


def test_cancel_requires_response_and_canceled_terminal_status(ros, monkeypatch):
    navigator = Navigator()
    result = Future()
    cancel = Future(SimpleNamespace(goals_canceling=[object()]), done=True)
    handle = SimpleNamespace(accepted=True, get_result_async=lambda: result,
                             cancel_goal_async=lambda: cancel)
    navigator.nav_to_pose_client.send_goal_async = lambda *args: Future(handle, done=True)
    navigator._feedbackCallback = lambda message: None
    canceled = threading.Event()

    def advance(node, future, timeout_sec):
        if not canceled.is_set():
            canceled.set()
        else:
            result.resolve(SimpleNamespace(status=GoalStatus.STATUS_CANCELED))

    monkeypatch.setattr(nav2_backend.rclpy, 'spin_until_future_complete', advance)
    assert nav2_backend.navigate_one_goal(navigator, 'map', region(), 1, 1, canceled) \
        is TaskResult.CANCELED


@pytest.mark.parametrize('cancel_response', [None, SimpleNamespace(goals_canceling=[])])
def test_unconfirmed_cancel_is_failure(ros, cancel_response):
    navigator = Navigator()
    result = Future()
    cancel = Future(cancel_response, done=cancel_response is not None)
    handle = SimpleNamespace(accepted=True, get_result_async=lambda: result,
                             cancel_goal_async=lambda: cancel)
    navigator.nav_to_pose_client.send_goal_async = lambda *args: Future(handle, done=True)
    navigator._feedbackCallback = lambda message: None
    canceled = threading.Event()
    monkey = nav2_backend.rclpy.spin_until_future_complete

    def request_cancel(*args, **kwargs):
        canceled.set()
        return monkey(*args, **kwargs)

    nav2_backend.rclpy.spin_until_future_complete = request_cancel
    try:
        assert nav2_backend.navigate_one_goal(navigator, 'map', region(), 1, 1, canceled) \
            is TaskResult.FAILED
    finally:
        nav2_backend.rclpy.spin_until_future_complete = monkey
