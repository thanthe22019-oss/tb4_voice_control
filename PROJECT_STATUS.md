# TB4 Voice Control — Recovery Handoff

> Canonical resume file for an interrupted Codex/subagent session. Read this
> file before changing code. Update it after every meaningful fix, review, or
> acceptance run.

## Snapshot

- Last updated: 2026-11-09 (Asia/Ho_Chi_Minh)
- Repository: `/home/alex/Interaction/tb4_voice_control`
- Active worktree: `/home/alex/Interaction/tb4_voice_control/.worktrees/implementation`
- Branch: `feature/implementation`
- Reviewed implementation head: `26c79e5203bd72935a8644f03cfa7482f292f7cb` (`fix: preserve cleanup ownership through finalization`).
- Base/bootstrap commit: `3161f4d`
- Source repository copied from: `/home/alex/Interaction/tb4_nav2`
- Source `tb4_nav2` was intentionally kept unchanged.

The cleanup-lifecycle code milestone has passed task reviews, final whole-plan
review plus scoped fix re-review, and fresh controller verification. Do **not**
claim the external hardware/live-simulation/GitHub items below are complete,
and do not merge or push without the user's explicit next-step choice.

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
- Persistent Nav2 cleanup ownership across late action acceptance, unresolved
  cancellation, CLI finalization, and warned operator force-abort.
- Cleanup-aware route admission and UI shutdown, including terminal-callback
  re-entry and exactly-once queued-close handling.
- Reproducible speech requirements for CUDA 12 cuBLAS and cuDNN 9 runtime
  wheels, with preflight guidance through the existing launcher environment.

## Last recorded automated evidence

CUDA runtime delivery verification on 2026-11-09:

- Focused delivery tests: 9 passed.
- Full `pytest -q` with ROS Humble sourced and Qt offscreen: 275 passed,
  1 skipped, 2 inherited deprecation warnings.
- Fresh `colcon build`: 1 package finished. Fresh `colcon test`: 275 passed,
  1 skipped; `colcon test-result --verbose`: 276 tests, 0 errors, 0 failures,
  1 skipped. Installed assets, six console entry points, and the no-op/reuse
  launch path were checked; venv `pip check` reports no broken requirements.
- One prior run failed
  `test_close_stops_active_recording_without_transcription` on a transcription
  timing assertion; its isolated rerun and the subsequent full suite passed.
- Speech venv NumPy was downgraded from 2.2.6 to 1.26.4 after the installed
  launcher exposed the system OpenCV NumPy ABI mismatch. Requirements now
  constrain `numpy<2`; `scripts/run_voice_control.sh --help` starts successfully.

Fresh controller verification on reviewed implementation head `26c79e5`, with
ROS Humble sourced and Qt offscreen:

- `pytest -q`: 271 passed, 1 skipped (two inherited deprecation warnings).
- `colcon build`: 1 package finished.
- `colcon test`: 271 passed, 1 skipped.
- `colcon test-result --verbose`: 272 tests, 0 errors, 0 failures, 1 skipped.
- `git diff --check`: clean.

These results were recorded on 2026-11-06 by the controller after the scoped
fix re-review. Run fresh verification again after any code change.

## GPU and speech runtime evidence

Host checks recorded on 2026-11-07:

- `nvidia-smi`: NVIDIA GeForce RTX 3050, driver `580.178.04`, CUDA driver API
  `13.0`.
- Speech venv created with `faster-whisper==1.2.1`,
  `ctranslate2==4.8.5`, and `sounddevice==0.5.6`.
- CTranslate2 outside the sandbox reports one CUDA device and supports
  `float16`.
- `WhisperModel('small', device='cuda', compute_type='float16')` loaded
  successfully; model data is cached under `.speech-model-cache/`.
- `pip check` reports no broken Python requirements after installing
  `pycryptodome` in the isolated speech venv.
- Host `arecord -l` detects `HD-Audio Generic / ALC257 Analog`.

Controller diagnostic evidence recorded on 2026-11-09:

- Microphone capture succeeded. CUDA inference initially failed because
  `libcublas.so.12` was missing.
- After installing NVIDIA CUDA 12 cuBLAS and cuDNN 9 wheels in the speech venv
  and setting launcher-equivalent `LD_LIBRARY_PATH`, end-to-end microphone
  capture → Faster-Whisper CUDA `float16` transcription exited 0.
- The observed text did not reliably match the spoken sample. This proves
  pipeline execution, not recognition quality or successful voice navigation.
  Recognition-quality validation and live simulator acceptance remain pending.

## Nav2 cleanup lifecycle

The backend retains and spins unresolved action cleanup, while the executor
and UI hold admission and defer ROS shutdown until cleanup is confirmed.
The operator can explicitly force local cleanup after a warning that remote
cancellation is unconfirmed; navigation stays disabled for the process.
The affected route remains failed rather than canceled or succeeded.

Task 1 and Task 2 passed independent review. The final whole-plan review found
three integration issues; commit `26c79e5` fixed all three, and the scoped
re-review marked every finding ADDRESSED with no new Critical/Important issue.

Relevant files:

- `tb4_voice_control/nav2_backend.py`
- `tb4_voice_control/route_executor.py`
- `tb4_voice_control/runtime_controller.py`
- `tb4_voice_control/qt_workers.py`
- `tb4_voice_control/voice_app.py`
- `tb4_voice_control/navigate_goals.py`
- `test/test_nav2_backend.py`
- `test/test_route_executor.py`
- `test/test_runtime_controller.py`
- `test/test_voice_app.py`
- `test/test_navigate_goals.py`

Review evidence (ignored SDD workspace):

- `.superpowers/sdd/2026-11-06-nav2-cleanup-lifecycle/progress.md`
- `.superpowers/sdd/2026-11-06-nav2-cleanup-lifecycle/task-1-review.md`
- `.superpowers/sdd/2026-11-06-nav2-cleanup-lifecycle/task-2-report.md`
- `.superpowers/sdd/2026-11-06-nav2-cleanup-lifecycle/task-2-review.md`
- `.superpowers/sdd/2026-11-06-nav2-cleanup-lifecycle/final-review.md`
- `.superpowers/sdd/2026-11-06-nav2-cleanup-lifecycle/final-fix-report.md`

Earlier milestone history:

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

Before editing, read this file, the current cleanup lifecycle ledger, and the
final review/fix report listed above; retain earlier milestone evidence for
historical context.
Do not reset or discard a dirty worktree. Preserve user changes.

After any code change, run the complete proof below before making a new
completion claim.

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

- NVIDIA/CUDA and microphone: end-to-end capture and CUDA `float16`
  transcription exited 0 on the RTX 3050, but recognition-quality validation
  remains pending because the observed text did not reliably match the sample.
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
- Cleanup-lifecycle implementation/review/automated verification is complete
  locally. Microphone-to-CUDA transcription execution is validated. The next
  milestone is recognition-quality validation plus live simulator acceptance, then
  GitHub publication when authentication/remote access is ready.

