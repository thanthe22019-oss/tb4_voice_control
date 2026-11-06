# TB4 Voice Control — Recovery Handoff

> Canonical resume file for an interrupted Codex/subagent session. Read this
> file before changing code. Update it after every meaningful fix, review, or
> acceptance run.

## Snapshot

- Last updated: 2026-11-06 (Asia/Ho_Chi_Minh)
- Repository: `/home/alex/Interaction/tb4_voice_control`
- Active worktree: `/home/alex/Interaction/tb4_voice_control/.worktrees/implementation`
- Branch: `feature/implementation`
- Task 2 base: `b3dbcb445889eb07b229b7a5ac6701bd81af1e97`; current head includes the Task 2 implementation commit containing this handoff.
- Base/bootstrap commit: `3161f4d`
- Source repository copied from: `/home/alex/Interaction/tb4_nav2`
- Source `tb4_nav2` was intentionally kept unchanged.

Do **not** merge, push, or claim final completion yet. Task 2 implementation
is complete; independent review and fresh controller verification are pending.

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

Task 2 implementation verification with ROS Humble sourced:

- Focused controller and UI: 13 and 14 passed, respectively.
- `pytest -q`: 262 passed, 1 skipped (two inherited deprecation warnings).
- `colcon build`: 1 package finished.
- `colcon test`: 262 passed, 1 skipped.
- `colcon test-result --verbose`: 263 tests, 0 errors, 0 failures, 1 skipped.

These are historical results. Run fresh verification before making any new
completion claim.

## Nav2 cleanup lifecycle

The backend retains and spins unresolved action cleanup, while the executor
and UI hold admission and defer ROS shutdown until cleanup is confirmed.
The operator can explicitly force local cleanup after a warning that remote
cancellation is unconfirmed; navigation stays disabled for the process.
The affected route remains failed rather than canceled or succeeded.

Task 1 has passed independent review. Task 2 needs independent review, then
a fresh whole-plan review and full verification by the controller session.

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

Review Task 2 and run the complete proof below in the controller session
before declaring completion.

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
- The next milestone is independent Task 2 and whole-plan review, followed
  by fresh full verification.

