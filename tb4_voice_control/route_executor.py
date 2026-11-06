"""Execute semantic route legs on one worker without importing ROS or Qt."""

from dataclasses import dataclass, replace
from enum import Enum
import logging
import threading
from typing import Callable, Protocol

from tb4_voice_control.regions import Region


class RouteState(Enum):
    """Observable route lifecycle; terminal routes may accept a new command."""

    IDLE = 'idle'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELED = 'canceled'


@dataclass(frozen=True)
class LegProgress:
    """One-based route position and optional navigation feedback for a region."""

    region_id: str
    leg_index: int = 0
    leg_count: int = 0
    distance_remaining: float | None = None
    elapsed_seconds: float | None = None


class NavigationBackend(Protocol):
    """A blocking leg executor that cooperatively observes cancellation."""

    def execute(self, region: Region, cancel_event: threading.Event,
                on_progress: Callable[[LegProgress], None]) -> RouteState:
        """Return SUCCEEDED, FAILED, or CANCELED after finishing one leg."""
        ...


class RouteExecutor:
    """Admit one route at a time; invoke callbacks on the route worker thread."""

    def __init__(self, backend: NavigationBackend, regions: tuple[Region, ...], *,
                 on_state: Callable[[RouteState], None] | None = None,
                 on_progress: Callable[[LegProgress], None] | None = None):
        """Snapshot the region catalog and optional controller callbacks."""
        self._backend = backend
        self._regions = {region.id: region for region in regions}
        self._on_state = on_state
        self._on_progress = on_progress
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._state = RouteState.IDLE
        self._worker = None

    @property
    def state(self) -> RouteState:
        """Read lifecycle state under the admission lock."""
        with self._lock:
            return self._state

    def start(self, region_ids: tuple[str, ...]) -> bool:
        """Start a route asynchronously, rejecting admission while RUNNING."""
        with self._lock:
            if self._state is RouteState.RUNNING:
                return False
            unknown = [identifier for identifier in region_ids
                       if identifier not in self._regions]
            if unknown:
                raise ValueError(f'Unknown region id(s): {", ".join(unknown)}')
            route = tuple(self._regions[identifier] for identifier in region_ids)
            self._cancel_event = threading.Event()
            self._state = RouteState.RUNNING
            self._worker = threading.Thread(
                target=self._run, args=(route, self._cancel_event),
                name='semantic-route', daemon=True)
            self._worker.start()
        return True

    def cancel(self) -> None:
        """Request cancellation; the worker owns all backend/ROS operations."""
        with self._lock:
            if self._state is RouteState.RUNNING:
                self._cancel_event.set()

    def wait(self, timeout: float | None = None) -> bool:
        """Join the current worker within a caller-selected shutdown budget."""
        with self._lock:
            worker = self._worker
        if worker is None:
            return True
        if worker is threading.current_thread():
            return False
        worker.join(timeout)
        return not worker.is_alive()

    @staticmethod
    def _notify(callback, value):
        """Keep a broken observer from leaving a navigation worker orphaned."""
        if callback is not None:
            try:
                callback(value)
            except Exception:
                logging.getLogger(__name__).exception('Route callback failed')

    def _run(self, route, cancel_event):
        result = RouteState.SUCCEEDED
        self._notify(self._on_state, RouteState.RUNNING)
        try:
            for index, region in enumerate(route, start=1):
                if cancel_event.is_set():
                    break

                def progress(update):
                    self._notify(self._on_progress, replace(
                        update, region_id=region.id, leg_index=index, leg_count=len(route)))

                progress(LegProgress(region.id))
                if cancel_event.is_set():
                    break
                result = self._backend.execute(region, cancel_event, progress)
                if result is not RouteState.SUCCEEDED:
                    if result is not RouteState.CANCELED:
                        result = RouteState.FAILED
                    break
        except Exception:
            logging.getLogger(__name__).exception('Route backend failed')
            result = RouteState.FAILED
        with self._lock:
            if cancel_event.is_set() and result is RouteState.SUCCEEDED:
                result = RouteState.CANCELED
            self._state = result
        self._notify(self._on_state, result)
