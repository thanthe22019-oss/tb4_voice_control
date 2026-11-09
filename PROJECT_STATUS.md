# TB4 Voice Control — Recovery Handoff

Updated 2026-11-09 (Asia/Ho_Chi_Minh). Active worktree:
`/home/alex/Interaction/tb4_voice_control/.worktrees/implementation`, branch
`feature/implementation`. Base/bootstrap commit: `3161f4d`; Gemini migration
implementation range: `d53fc62..577d874` plus the Task 3 delivery commit.
The original `tb4_nav2` source remains unchanged.

The automated Gemini integration is complete locally: push-to-talk sends audio
to Gemini, configured through `config/voice.yaml`; setup and launcher use a
separate speech venv and the `GEMINI_API_KEY` environment variable. The UI,
semantic regions, parser, route executor and Nav2 cleanup lifecycle are retained.
Speech audio is sent to Google, requiring Internet and quota. Never record a key
in this file or commit one.

## Fresh offline verification

On 2026-11-09, with ROS Humble sourced and Qt offscreen:

- Focused delivery tests: 14 passed.
- Full pytest: 304 passed, 1 skipped, 2 inherited deprecation warnings.
- Colcon build: 1 package finished. Colcon test: 304 passed, 1 skipped,
  2 inherited deprecation warnings. Test result: 305 tests, 0 errors,
  0 failures, 1 skipped; one package emitted the same warnings on stderr.

## Pending acceptance and publication

- Real-key Gemini transcription of the three Vietnamese commands, including
  correctness and latency, remains pending. Unknown-region UI error and absence
  of a Nav2 goal also require live evidence. See `docs/TEST_MATRIX.md`.
- Live TurtleBot 4/Nav2 simulation acceptance remains pending.
- GitHub publication and video remain pending; no public remote is verified.
- The academic HTML/PDF report remains deferred and outside this milestone.

Historical CUDA and microphone runs, plans and reviews are evidence of the old
provider only and do not establish current Gemini acceptance. Their details
remain in repository history and the explicitly marked historical plans/specs.
Do not merge or publish without the user's next-step choice.

## Resume

Inspect `git status`, source `/opt/ros/humble/setup.bash`, and follow README for
build, setup and operator workflow. Preserve existing changes. Re-run the full
pytest and colcon proof after changes; update this file with fresh evidence.
