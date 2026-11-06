# TB4 Voice Control — Recovery Handoff

> Canonical resume file for an interrupted Codex/subagent session. Read this
> file before changing code. Update it after every meaningful fix, review, or
> acceptance run.

## Snapshot

- Last updated: 2026-11-06 (Asia/Ho_Chi_Minh)
- Repository: `/home/alex/Interaction/tb4_voice_control`
- Active worktree: `/home/alex/Interaction/tb4_voice_control/.worktrees/implementation`
- Branch: `feature/implementation`
- Current code head before this handoff commit: `216d6d1`
- Base/bootstrap commit: `3161f4d`
- Source repository copied from: `/home/alex/Interaction/tb4_nav2`
- Source `tb4_nav2` was intentionally kept unchanged.

Do **not** merge, push, or claim the code scope complete yet. One Important
Nav2 action-lifecycle finding remains open.

## What is implemented

- Manual polygon Map Editor using PyQt5/OpenCV, including Unicode region
  labels, goal editing, visibility, undo, YAML persistence, and rendered map
  export.
- Occupancy-map pixel/world conversion with origin yaw and cell-center
  semantics.
- Semantic regions, aliases, overlap/occupancy/goal validation, and three
  sample regions.
- Deterministic Vietnamese command parsing for GO_TO and FROM_TO, including
  ambiguity and unknown-region handling.
- Asynchronous route execution and a ROS 2 Humble Nav2 backend.
- Push-to-talk audio adapter and lazy `faster-whisper` adapter configured for
  `small`, `cuda`, `float16`, and Vietnamese.
- Runtime controller, Qt workers, voice-control UI, cancellation, deferred UI
  close, and bounded worker shutdown.
- ROS launch, installed assets, speech virtual-environment scripts, README,
  demo checklist, test matrix, and six console entry points.
- Runtime semantic-map validation, missing-localization error/retry behavior,
  integer YAML coordinate conversion, and bounded Nav2 action waits.

## Last recorded automated evidence

The final fix implementer recorded the following at commit `216d6d1`:

- `pytest -q`: 241 passed, 1 skipped.
- `colcon build`: 1 package finished.
- `colcon test`: 241 passed, 1 skipped.
- `colcon test-result --verbose`: 242 tests, 0 errors, 0 failures, 1 skipped.

These are historical results. Run fresh verification before making any new
completion claim.

## Open Important finding — must fix next

The Nav2 backend now bounds server discovery, goal send/accept, result, and
cancel waits and reports unconfirmed cancellation as failure. However, when a
send-goal response or cancel response remains pending after the route returns
`FAILED`, there is no persistent cleanup owner/spinner.

Consequences confirmed by the scoped final review:

1. The UI/controller can accept another route while the previous action
   response is still unresolved.
2. A late goal acceptance callback only progresses if something later spins
   the ROS node.
3. Closing the application can destroy the node before cleanup is confirmed.
4. A late accepted goal may therefore coexist with a newer goal or remain
   unconfirmed remotely.

Required behavior for the follow-up fix:

- Retain ownership of unresolved action cleanup after the route worker returns.
- Continue spinning cleanup safely without concurrent `rclpy` spinning.
- Reject new route admission while cleanup is unresolved.
- Keep shutdown from destroying the ROS node while normal cleanup is pending.
- Define an explicit operator force-abort policy for transport that never
  responds; never label this state as confirmed cancellation.
- Re-enable command admission only after a known terminal/cleanup state.
- Add regression tests proving late acceptance, pending/rejected cancel,
  second-command rejection, and shutdown behavior.

Relevant files:

- `tb4_voice_control/nav2_backend.py`
- `tb4_voice_control/route_executor.py`
- `tb4_voice_control/runtime_controller.py`
- `tb4_voice_control/qt_workers.py`
- `tb4_voice_control/voice_app.py`
- `test/test_nav2_backend.py`
- `test/test_route_executor.py`
- `test/test_runtime_controller.py`
- `test/test_voice_app.py`

Review evidence (ignored SDD workspace):

- `.superpowers/sdd/2026-11-02-tb4-voice-control/final-branch-review.md`
- `.superpowers/sdd/2026-11-02-tb4-voice-control/final-fix-report.md`
- `.superpowers/sdd/2026-11-02-tb4-voice-control/progress.md`

## Resume procedure

```bash
cd /home/alex/Interaction/tb4_voice_control/.worktrees/implementation
git status --short
git branch --show-current
git log -8 --oneline
source /opt/ros/humble/setup.bash
```

Before editing, read this file and the three SDD evidence files listed above.
Do not reset or discard a dirty worktree. Preserve user changes.

Use TDD for the remaining Nav2 lifecycle issue:

1. Add focused failing tests for cleanup ownership/admission/shutdown.
2. Confirm the expected RED failure.
3. Implement the smallest coherent lifecycle fix.
4. Run the focused tests.
5. Run the complete proof below.
6. Request an independent scoped review before declaring completion.

Complete proof:

```bash
source /opt/ros/humble/setup.bash
QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD:$PYTHONPATH" pytest -q
colcon build --base-paths . --packages-select tb4_voice_control --symlink-install
colcon test --base-paths . --packages-select tb4_voice_control \
  --event-handlers console_direct+
colcon test-result --verbose
```

Also verify installed entry points/assets and the no-op/reuse launch path after
any packaging or launch change.

## External blockers and intentionally deferred work

- NVIDIA/CUDA: blocked in the current environment; `nvidia-smi` previously
  exited 9 because the driver could not communicate.
- Microphone: blocked; `arecord -l` previously found no soundcards.
- Live TurtleBot 4/Nav2 simulation acceptance: not run yet.
- GitHub: `gh` authentication was invalid and no remote was configured. Do not
  store tokens in the repository.
- Academic HTML/PDF report: explicitly deferred by the user because the report
  requirements changed. Do not recreate the old draft.
- Optional Task 11 multi-waypoint extension: do not start until required live
  acceptance is stable.

Never claim any blocked/manual item passed without new evidence.

## Delivery state

- Local feature branch only; not merged to `main`.
- No public GitHub repository/remote has been verified.
- The academic report is not part of the current code milestone.
- The next milestone is solely the unresolved Nav2 cleanup lifecycle, its
  tests, independent review, and fresh full verification.

