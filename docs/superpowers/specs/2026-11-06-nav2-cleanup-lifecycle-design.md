# Nav2 Cleanup Lifecycle Design

## Intent

Complete the remaining Nav2 action-lifecycle gap without rewriting the
working voice-navigation architecture. A route must not be admitted while a
previous action has an unresolved send/cancel/result future, and normal
application shutdown must retain the ROS node until cleanup reaches a known
terminal state.

## Goals

- Give `BasicNavigatorBackend` explicit ownership of unresolved action cleanup.
- Keep exactly one owner spinning the navigator at a time.
- Reject new routes while cleanup is pending.
- Keep normal shutdown from destroying ROS while cleanup is pending.
- Re-enable route admission only after a known terminal cleanup state.
- Provide an explicit operator force-abort path for a transport that never
  responds, without reporting cancellation as confirmed.
- Prove late acceptance, pending/rejected cancellation, second-command
  rejection, normal cleanup, and shutdown behavior with deterministic tests.

## Non-goals

- No redesign of the parser, region model, Map Editor, speech pipeline, or
  launch/package layout.
- No live robot, simulator, microphone, CUDA, GitHub, academic report, or
  optional multi-waypoint work in this change.
- No claim that a destroyed ROS client can remotely cancel a goal when the
  transport never responds.

## Constraints

- Ubuntu 22.04, ROS 2 Humble, Python, PyQt5, and the existing
  `nav2_simple_commander` integration remain unchanged.
- ROS spinning for this navigator must not occur concurrently.
- Public callbacks must never run while internal locks are held.
- Ordinary waits and UI close operations remain bounded per attempt; an
  unresolved transport is represented explicitly, not disguised as success or
  confirmed cancellation.
- Existing automated behavior and installed entry points must remain intact.

## Approaches considered

### 1. Backend-owned cleanup worker — selected

`BasicNavigatorBackend` owns the unresolved action future and a single cleanup
worker. The worker retains the navigator I/O claim, spins late responses, and
requests/verifies cancellation when a goal is accepted late. Backend
quiescence is an explicit contract consumed by route admission and shutdown.

This is the smallest change at the layer that owns the ROS action futures. It
avoids moving ROS details into the pure executor/controller while preserving
one-spin-owner semantics.

### 2. Keep `RouteExecutor` in a CLEANING state

This would prevent route admission but make the pure executor responsible for
ROS cleanup duration and could keep its route worker alive indefinitely. It
also weakens the existing separation between pure route state and ROS I/O.

### 3. Dedicated ROS I/O actor for every operation

Serializing pose, readiness, navigation, and cleanup through one actor is a
strong long-term architecture, but it requires a broad late-stage refactor and
creates unnecessary regression risk for this single remaining defect.

## Selected design

### Backend cleanup ownership

The backend exposes an explicit quiescence contract, conceptually:

- `cleanup_pending`: whether an unresolved action still owns ROS cleanup.
- `wait_for_cleanup(timeout)`: bounded wait for a known terminal cleanup state.
- `force_abort_cleanup()`: abandon local ownership only after an explicit
  operator decision; the resulting status remains indeterminate/failed.

Exact names may follow existing code conventions, but these semantics are
binding.

When goal acceptance, cancellation acknowledgement, or terminal result misses
the normal deadline, `execute()` returns failure to the route while transferring
the unresolved future/goal handle to the backend cleanup owner. The cleanup
worker retains exclusive navigator spinning, observes late acceptance, issues
cancel when possible, and verifies the response and terminal result. It then
marks the backend quiescent and wakes waiters.

The backend must not start a second cleanup worker or allow a second navigation
operation while cleanup is pending.

### Admission behavior

`RouteExecutor.start()` (or the narrow backend-admission boundary it calls)
must reject a route if the backend is not quiescent. `RuntimeController`
surfaces a clear Vietnamese error/status and keeps navigation controls disabled
until cleanup completes. Completion notification may be polled or delivered by
an existing safe callback/signal path, but callbacks run outside locks.

### Shutdown behavior

Normal close first closes speech/navigation admission and requests route
cancellation as today. It then waits for both the route worker and backend
cleanup quiescence before destroying the ROS node.

If cleanup never resolves, the window remains alive and shows that Nav2 cleanup
is still pending. An explicit force-abort action may allow exit, but it must:

- warn that remote cancellation is unconfirmed;
- disable future route admission permanently for that process;
- never publish a CANCELED/SUCCEEDED result for the unresolved goal;
- destroy ROS only after the operator chooses the force path.

No automatic timeout silently converts pending cleanup into safe shutdown.

### Error and state semantics

- A route whose action cleanup is unresolved ends as `FAILED`, not `CANCELED`.
- Backend state remains cleanup-pending after that route result.
- A second command receives zero Nav2 action requests.
- Confirmed terminal cleanup restores quiescence and permits a later command.
- Force-abort ends local cleanup ownership but leaves an explicit indeterminate
  error in the UI/logs.

## Tests

Use fake Humble-style action futures and deterministic synchronization; no ROS
graph or hardware is required.

- Late send acceptance is spun by the cleanup owner, canceled, and verified.
- Pending/rejected cancel keeps cleanup pending or produces an explicit
  indeterminate failure according to the transport state.
- A second route is rejected and sends zero action requests while cleanup is
  pending.
- Route admission returns after confirmed cleanup.
- Normal window close does not call ROS shutdown while cleanup is pending.
- Confirmed cleanup allows deferred close to finish exactly once.
- Force-abort requires an explicit UI/operator action and never reports
  confirmed cancellation.
- Existing route, controller, UI, full pytest, colcon build, and colcon test
  proofs remain green.

## Recovery and delivery

Update `PROJECT_STATUS.md` after implementation, review, and verification.
The change is not complete until an independent reviewer approves the scoped
diff and fresh full verification passes.

