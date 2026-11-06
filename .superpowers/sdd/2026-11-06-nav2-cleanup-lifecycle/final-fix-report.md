# Final fix report

## Final fix wave

Base: `038351c8e706ee9b3f13b823f203b3fb61e9efc0`.
Status: all three whole-plan findings addressed; scoped independent re-review
and fresh controller-session acceptance remain pending. No push or merge.

### Findings addressed and design decisions

1. **Important: CLI teardown during unresolved cleanup.** The CLI retains the
   navigator and ROS context while backend cleanup is PENDING, using bounded
   `wait_for_cleanup(0.1)` attempts. It warns that remote cancellation is
   unconfirmed and that the robot may still move; pressing Ctrl+C after this
   warning explicitly requests backend force-abort. A timeout alone never
   releases ownership. The existing backend force operation joins its cleanup
   owner and permanently disables admission before the CLI destroys ROS.
   Confirmed cleanup and force both retain exit 4 for the failed action.

   ROS's automatic signal handlers would shut down its context before this
   contract could be honored, so the CLI initializes with
   `SignalHandlerOptions.NO`. Its temporary SIGINT/SIGTERM handlers request
   cooperative cancellation during readiness/navigation. During the warned
   cleanup wait, only SIGINT requests force; SIGTERM does not silently force.
   Original handlers are restored after finalization. Cooperative interruption
   preserves exit 130 when the backend finishes without an indeterminate
   failure. Existing bad-file/readiness/failure/KeyboardInterrupt exit tests
   remain intact; the compatibility KeyboardInterrupt case still passes.

2. **Important: rejected terminal-callback command strands runtime.** Removed
   the speculative NAVIGATING transition before `RouteExecutor.start()`.
   The accepted executor's existing RUNNING callback owns this transition.
   When a terminal listener submits while the prior worker is returning,
   admission rejects without changing the terminal runtime state; a later
   command succeeds. This avoids synthesizing another terminal notification
   that could recursively trigger the same listener. The executor's live-worker
   and cleanup admission checks, wait ownership, and shutdown protocol stay
   intact. Regressions cover SUCCEEDED, CANCELED, and FAILED/ERROR.

3. **Minor: queued close retry calls shutdown twice.** Both the retry and
   finalization paths return immediately after `_shutdown_done`. Successful
   finalization marks the flag before invoking the injected shutdown callback,
   also protecting against reentrant callback work. The regression captures the
   pending timer, completes a second close after confirmed cleanup, then drains
   the original retry through Qt's event loop and observes one callback.

### Test-first RED evidence

The TDD skill and its writing-good-tests reference were read before edits.
All new regression groups below were run against the unchanged production
base, before production implementation. Each command ran in
`/home/alex/Interaction/tb4_voice_control/.worktrees/implementation`.

```bash
source /opt/ros/humble/setup.bash && PYTHONPATH="$PWD:$PYTHONPATH" pytest -q test/test_navigate_goals.py -k pending_cleanup
```

Result: **2 failed, 12 deselected in 0.64s**. Both confirmed/forced-release
cases failed in `destroy()` because cleanup was still `CleanupState.PENDING`.
Neither had reached a cleanup wait. This directly reproduces unsafe teardown.

```bash
source /opt/ros/humble/setup.bash && PYTHONPATH="$PWD:$PYTHONPATH" pytest -q test/test_runtime_controller.py -k terminal_listener
```

Result: **3 failed, 13 deselected in 0.63s**. Each terminal case observed
`RuntimeState.NAVIGATING` instead of its expected terminal state after the
listener's rejected command and prior worker exit.

```bash
source /opt/ros/humble/setup.bash && QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD:$PYTHONPATH" pytest -q test/test_voice_app.py -k queued_close_retry
```

Result: **1 failed, 16 deselected in 0.69s**. Draining the queued retry after
successful close produced shutdown calls `[True, True]`, expected `[True]`.

Before implementing signal behavior, added the cooperative SIGINT case to the
existing exit-code regression and ran:

```bash
source /opt/ros/humble/setup.bash && PYTHONPATH="$PWD:$PYTHONPATH" pytest -q test/test_navigate_goals.py -k preserves_exit
```

Result: **1 failed, 5 passed, 9 deselected in 0.59s**. The original SIGINT
handler raised KeyboardInterrupt and caused the CLI to call `cancelTask()`
instead of signaling the backend's cancellation event (cancel count 1,
expected 0). The five inherited exit cases passed. The new case's GREEN path
also asserts that the backend's cancel event is set before returning CANCELED.

### GREEN and full verification evidence

After the implementation, focused amended files:

```bash
source /opt/ros/humble/setup.bash && QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD:$PYTHONPATH" pytest -q test/test_navigate_goals.py test/test_runtime_controller.py test/test_voice_app.py
```

Result: **48 passed in 1.07s**. CLI pending tests assert zero destruction or
ROS shutdown in both bounded pending waits, exactly one final destroy/shutdown
after confirmation or explicit force, the warning before force, exit 4,
restoration of the SIGINT handler, and disabling ROS's automatic handlers.
The doubles have bounded failure guards, so a broken force path cannot hang
these tests. Controller regressions use the real executor and its actual
terminal callback; Qt regression drains a real queued timer callback. No new
timing sleeps were introduced.

```bash
source /opt/ros/humble/setup.bash && QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD:$PYTHONPATH" pytest -q
```

Result: **271 passed, 1 skipped, 2 warnings in 5.66s**. The skip is inherited
`test/test_copyright.py`; both warnings are the existing SelectableGroups
deprecation from `test/test_flake8.py`. No failures, errors, or hangs.

```bash
source /opt/ros/humble/setup.bash && colcon build --base-paths . --packages-select tb4_voice_control --symlink-install
```

Result: **1 package finished [1.42s]**, exit 0.

```bash
source /opt/ros/humble/setup.bash && QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD:$PYTHONPATH" colcon test --base-paths . --packages-select tb4_voice_control --event-handlers console_direct+
```

Result: **271 passed, 1 skipped, 2 warnings in 5.88s**; colcon **1 package
finished [30.3s]**, exit 0. Its stderr summary contains the same two inherited
deprecation warnings, not a test failure.

```bash
source /opt/ros/humble/setup.bash && colcon test-result --verbose && git diff --check
```

Result: **272 tests, 0 errors, 0 failures, 1 skipped**; diff check clean.

### Files changed

- `tb4_voice_control/navigate_goals.py`
- `tb4_voice_control/runtime_controller.py`
- `tb4_voice_control/voice_app.py`
- `test/test_navigate_goals.py`
- `test/test_runtime_controller.py`
- `test/test_voice_app.py`
- `.superpowers/sdd/2026-11-06-nav2-cleanup-lifecycle/final-fix-report.md`

### Self-review and remaining concerns

- Cleanup ownership: no second ROS spinner or action owner was introduced.
  CLI readiness/execution share one cooperative event; finalization only waits
  on the existing backend contract or explicitly calls its force operation.
  Normal teardown cannot cross PENDING, and no timeout is called cancellation.
- Exactly-once shutdown: queued retries are harmless after finalization;
  the callback guard is set before invocation. Actual node destruction and ROS
  shutdown remain after route and QThread completion in the window.
- Qt threads: all widget changes and retry/finalization flags remain on the
  Qt thread. The timer test requeues the captured callback into that event loop.
  Existing background force handling remains unchanged.
- Locks/callbacks: no callbacks were moved under locks. The controller relies
  on existing executor notifications outside its admission lock. It neither
  clears the old worker early nor weakens cleanup admission to solve the race.
- Test totals rose from 264 to 271 passes: two CLI cleanup cases, one
  cooperative interrupt case, three terminal outcomes, and one queued retry.
- No outstanding issue found in this self-review. The CLI intentionally waits
  indefinitely across bounded attempts if cleanup never resolves until the
  operator uses the warned Ctrl+C force path. SIGKILL/process termination
  cannot guarantee remote cancellation and is outside this contract.
- These are implementation-session results, not independent acceptance. Live
  DDS/robot/simulator, GPU, microphone, GitHub publication, and academic-report
  validation were not performed. Scoped re-review and controller-session fresh
  full verification remain the parent workflow's completion gate.
