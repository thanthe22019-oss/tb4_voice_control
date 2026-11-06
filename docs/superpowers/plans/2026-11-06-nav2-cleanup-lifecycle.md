# Nav2 Cleanup Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retain ownership of unresolved Nav2 action cleanup, block conflicting routes and unsafe shutdown, and provide an explicit force-abort path without claiming unconfirmed cancellation.

**Architecture:** `BasicNavigatorBackend` owns the ROS cleanup worker and serializes all navigator spinning. `RouteExecutor` exposes cleanup as a pure lifecycle state and holds route admission closed until backend cleanup reaches a terminal local state. `RuntimeController` and the Qt window render that state, keep normal close deferred, and expose an explicit warned force-abort operation.

**Tech Stack:** Python 3.10, ROS 2 Humble (`rclpy`, `nav2_simple_commander`), PyQt5, pytest, colcon.

**Spec:** `docs/superpowers/specs/2026-11-06-nav2-cleanup-lifecycle-design.md`

## Global Constraints

- Keep Ubuntu 22.04, ROS 2 Humble, Python, PyQt5, and the existing `nav2_simple_commander` integration.
- Exactly one owner may spin the backend navigator at a time.
- Public callbacks and Qt signals must be emitted outside internal locks.
- A missing/unresolved transport response is never reported as confirmed cancellation.
- Normal route admission and normal ROS shutdown remain blocked while cleanup is pending.
- Force-abort is explicit, warned, permanently disables route admission for that process, and leaves the route result failed/indeterminate.
- No live robot, simulator, CUDA, microphone, GitHub, academic report, or Task 11 work belongs to this plan.
- Use TDD for every behavior change and preserve all existing automated/install behavior.

## Review Focus

- Send-goal response arrives after the route deadline: cleanup must keep spinning, cancel the accepted goal, and verify a terminal result.
- Cancel acknowledgement is rejected or never arrives: no second route and no normal shutdown may proceed.
- Cleanup completes while the UI is waiting to close: shutdown must occur exactly once without operator force-abort.
- Operator force-aborts a permanently unresponsive transport: local shutdown may proceed, but future routes remain disabled and cancellation stays unconfirmed.
- Cleanup and pose/readiness work become ready concurrently: navigator spinning must remain single-owner without deadlock.

---

### Task 1: Own unresolved Nav2 cleanup and gate pure route admission

**Files:**
- Modify: `tb4_voice_control/nav2_backend.py`
- Modify: `tb4_voice_control/route_executor.py`
- Test: `test/test_nav2_backend.py`
- Test: `test/test_route_executor.py`

**Interfaces:**
- Consumes: Humble action futures returned by `send_goal_async()`, `cancel_goal_async()`, and `get_result_async()`; existing `BasicNavigatorBackend.execute()` and `RouteExecutor.start()/cancel()/wait()`.
- Produces: `CleanupState` enum with `QUIESCENT`, `PENDING`, and `FORCE_ABORTED`; optional cleanup-aware backend contract `cleanup_state`, `wait_for_cleanup(timeout: float | None) -> CleanupState`, and `force_abort_cleanup() -> bool`; `RouteState.CLEANING`; `RouteExecutor.cleanup_state` and `RouteExecutor.force_abort_cleanup()`.

- [ ] **Step 1: Write failing backend cleanup-owner tests**

Add focused tests using Humble-shaped fake futures/action handles:

- `test_late_acceptance_is_owned_until_confirmed_terminal_cancel`
- `test_pending_or_rejected_cancel_keeps_backend_cleanup_pending`
- `test_force_abort_releases_waiter_but_permanently_disables_admission`
- `test_cleanup_worker_never_spins_concurrently_with_navigation_or_pose_poll`

Assert `CleanupState.PENDING` immediately after an unresolved action returns failure, continued spinning after the route call returns, verified cancel response plus `GoalStatus.STATUS_CANCELED` before `QUIESCENT`, and `FORCE_ABORTED` when explicitly requested.

- [ ] **Step 2: Run backend tests to verify RED**

Run:

```bash
source /opt/ros/humble/setup.bash
PYTHONPATH="$PWD:$PYTHONPATH" pytest -q \
  test/test_nav2_backend.py -k "cleanup or late_acceptance or force_abort"
```

Expected: FAIL because unresolved futures currently have no persistent cleanup owner/state.

- [ ] **Step 3: Implement backend cleanup ownership**

In `nav2_backend.py`:

- Import `CleanupState` from the pure executor module.
- Add cleanup condition/state, force event, and at most one daemon cleanup worker to `BasicNavigatorBackend`.
- Transfer unresolved send/cancel/result futures to an internal cleanup record before the normal route call releases ownership.
- Let the cleanup worker acquire the existing navigator I/O claim and spin until rejection or a known terminal result; cancel late accepted goals and verify acknowledgement/result.
- Keep state `PENDING` while the transport remains unresolved; transition to `QUIESCENT` only after a known terminal outcome.
- `force_abort_cleanup()` transitions `PENDING` to `FORCE_ABORTED`, wakes waiters, and permanently prevents `execute()`/readiness from dispatching another goal.
- Never invoke user callbacks while holding cleanup/I/O locks.

The implementation may introduce one private cleanup dataclass/helper, but must not add a second ROS node or a second concurrent spinner.

- [ ] **Step 4: Run backend tests to verify GREEN**

Run:

```bash
source /opt/ros/humble/setup.bash
PYTHONPATH="$PWD:$PYTHONPATH" pytest -q test/test_nav2_backend.py
```

Expected: all backend tests PASS.

- [ ] **Step 5: Write failing executor admission tests**

Add:

- `test_cleanup_pending_keeps_executor_cleaning_and_rejects_second_route`
- `test_confirmed_cleanup_finishes_failed_route_and_allows_retry`
- `test_force_abort_finishes_wait_but_never_restores_route_admission`

Assert the transition `RUNNING -> CLEANING -> FAILED`, `start()` returns false and sends zero backend requests during cleanup, `wait()` remains false while cleanup is pending, and only confirmed `QUIESCENT` cleanup permits a retry.

- [ ] **Step 6: Run executor tests to verify RED**

Run:

```bash
PYTHONPATH="$PWD:$PYTHONPATH" pytest -q test/test_route_executor.py -k cleanup
```

Expected: FAIL because the executor currently treats backend failure as immediately terminal and admits a new route.

- [ ] **Step 7: Implement the pure cleanup-aware route lifecycle**

In `route_executor.py`:

- Define `CleanupState` and `RouteState.CLEANING` without importing ROS or Qt.
- Treat backends without the optional cleanup interface as `QUIESCENT` for existing pure test doubles.
- When a failed leg leaves backend cleanup `PENDING`, notify `CLEANING`, wait on the backend condition in the existing route worker, then finish `FAILED`.
- Reject `start()` unless the worker is gone and backend cleanup is `QUIESCENT`.
- Delegate explicit force-abort through `force_abort_cleanup()`; a forced backend remains permanently inadmissible.

- [ ] **Step 8: Run Task 1 focused and regression tests**

Run:

```bash
source /opt/ros/humble/setup.bash
PYTHONPATH="$PWD:$PYTHONPATH" pytest -q \
  test/test_nav2_backend.py test/test_route_executor.py
```

Expected: all focused tests PASS with no hanging worker.

- [ ] **Step 9: Commit Task 1**

```bash
git add tb4_voice_control/nav2_backend.py tb4_voice_control/route_executor.py \
  test/test_nav2_backend.py test/test_route_executor.py
git commit -m "fix: retain ownership of pending Nav2 cleanup"
```

---

### Task 2: Surface cleanup state in the controller and make UI shutdown safe

**Files:**
- Modify: `tb4_voice_control/runtime_controller.py`
- Modify: `tb4_voice_control/qt_workers.py`
- Modify: `tb4_voice_control/voice_app.py`
- Modify: `PROJECT_STATUS.md`
- Test: `test/test_runtime_controller.py`
- Test: `test/test_voice_app.py`

**Interfaces:**
- Consumes: Task 1 `RouteState.CLEANING`, `CleanupState`, `RouteExecutor.cleanup_state`, and `RouteExecutor.force_abort_cleanup()`.
- Produces: `RuntimeState.CLEANING`; `RuntimeController.force_abort_cleanup() -> bool`; Qt/UI cleanup status propagation; an explicit force-abort button/action that is available only while cleanup is pending.

- [ ] **Step 1: Write failing runtime-controller tests**

Add:

- `test_cleanup_state_disables_text_and_sends_zero_second_goals`
- `test_confirmed_cleanup_restores_admission_after_failed_route`
- `test_force_abort_is_explicit_and_permanently_rejects_routes`

Assert `RuntimeState.CLEANING`, a Vietnamese actionable error/status, zero backend requests for the second command, and no callback invocation under admission locks.

- [ ] **Step 2: Run controller tests to verify RED**

Run:

```bash
PYTHONPATH="$PWD:$PYTHONPATH" pytest -q test/test_runtime_controller.py -k cleanup
```

Expected: FAIL because cleanup is not currently represented by the runtime state machine.

- [ ] **Step 3: Implement cleanup-aware controller state**

In `runtime_controller.py` and `qt_workers.py`:

- Map `RouteState.CLEANING` to `RuntimeState.CLEANING`.
- Keep text/speech route admission closed while cleanup is pending.
- Expose `force_abort_cleanup()` and propagate state/error callbacks outside locks.
- Keep failed/indeterminate semantics after force-abort; do not emit canceled or succeeded.

- [ ] **Step 4: Run controller tests to verify GREEN**

Run:

```bash
PYTHONPATH="$PWD:$PYTHONPATH" pytest -q test/test_runtime_controller.py
```

Expected: all controller tests PASS.

- [ ] **Step 5: Write failing offscreen UI/shutdown tests**

Add:

- `test_cleanup_pending_keeps_controls_disabled_and_close_deferred`
- `test_confirmed_cleanup_closes_and_shuts_ros_down_once`
- `test_force_abort_requires_warning_and_never_reenables_navigation`

Use fake cleanup-aware backend futures. Assert normal close is ignored and ROS shutdown count stays zero while pending; confirmed cleanup completes deferred close exactly once; force-abort requires an explicit confirmation action, displays an indeterminate warning, finishes local shutdown, and leaves navigation permanently disabled.

- [ ] **Step 6: Run UI tests to verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD:$PYTHONPATH" \
  pytest -q test/test_voice_app.py -k cleanup
```

Expected: FAIL because the UI currently treats route failure as terminal and has no explicit force-abort control.

- [ ] **Step 7: Implement the warned force-abort UI and deferred close**

In `voice_app.py`:

- Add a cleanup/force-abort control hidden outside `RuntimeState.CLEANING`.
- Keep record/text/send/cancel disabled while cleanup is pending.
- Confirm force-abort with a modal warning stating that remote cancellation is unconfirmed.
- Call `RuntimeController.force_abort_cleanup()` only after confirmation.
- Keep the existing close retry loop; allow ROS destruction only after the route worker exits following confirmed cleanup or explicit force-abort.
- Never re-enable navigation after force-abort in the same process.

- [ ] **Step 8: Update the tracked recovery handoff**

Update `PROJECT_STATUS.md` with the new head, cleanup contract, focused/full test results, and remaining external blockers. Remove the old open-finding text only after the focused tests pass; mark independent review and fresh full verification as pending until they actually occur.

- [ ] **Step 9: Run the complete automated proof**

Run:

```bash
source /opt/ros/humble/setup.bash
QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD:$PYTHONPATH" pytest -q
colcon build --base-paths . --packages-select tb4_voice_control --symlink-install
colcon test --base-paths . --packages-select tb4_voice_control \
  --event-handlers console_direct+
colcon test-result --verbose
```

Expected: pytest and colcon tests have zero failures/errors; only the inherited skip is allowed.

- [ ] **Step 10: Commit Task 2**

```bash
git add tb4_voice_control/runtime_controller.py tb4_voice_control/qt_workers.py \
  tb4_voice_control/voice_app.py PROJECT_STATUS.md \
  test/test_runtime_controller.py test/test_voice_app.py
git commit -m "fix: gate voice runtime on Nav2 cleanup"
```

---

## Completion Gate

- Each task receives an independent spec/code-quality review.
- Any Important/Critical finding enters the bounded fix loop.
- After both task reviews are clean, run a fresh whole-plan review of the
  follow-up diff and a fresh full verification from the controller session.
- Do not merge or push automatically.
- Do not delete the recovery handoff; update it with the reviewed commit and
  remaining hardware/external work.

