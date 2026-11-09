# TB4 Voice Control — Recovery Handoff

Updated 2026-11-09 (Asia/Ho_Chi_Minh). Active worktree:
`/home/alex/Interaction/tb4_voice_control/.worktrees/implementation`, branch
`feature/implementation`. Base/bootstrap commit: `3161f4d`; Gemini migration
reviewed migration range: `d53fc62..bb5e637`. Subsequent SDK compatibility fix:
`d71307e07b8f1621eea7ecbc0209650f754e5cd7` (fresh proof below, separate from
the reviewed milestone).
The original `tb4_nav2` source remains unchanged.

The automated Gemini integration and offline SDK acceptance are complete locally:
push-to-talk uses the Generate Content API on `google-genai>=2.33,<2.34`,
configured through `config/voice.yaml`; setup and launcher use a
separate speech venv and the `GEMINI_API_KEY` environment variable. The UI,
semantic regions, parser, route executor and Nav2 cleanup lifecycle are retained.
Speech audio is sent to Google, requiring Internet and quota. Never record a key
in this file or commit one.

## Fresh offline verification

On 2026-11-09, for SDK compatibility implementation `d71307e`, with ROS Humble
sourced and Qt offscreen:

- Focused speech/SDK/delivery tests: 50 passed.
- Explicit actual-SDK acceptance: 9 passed with Python 3.10.12 and
  google-genai 2.33.0 in `.venv-speech`. Synthetic key + MockTransport only;
  one request and zero retry sleep for 429 (Retry-After: 3600), 500, 503,
  connection and timeout failures. Inline WAV, store=False, 1.25-second test
  timeout, text extraction and disabled continuation were also verified.
- Full portable ROS pytest: 308 passed, 10 skipped, 2 inherited deprecation
  warnings. Skips are the existing copyright check plus 9 opt-in SDK tests.
- Colcon build: 1 package finished. Colcon test: 308 passed, 10 skipped,
  2 inherited warnings. Test result: 318 tests, 0 errors, 0 failures,
  10 skipped; one package emitted the same warnings on stderr.
- `.venv-speech/bin/python -m pip check`, Bash syntax and `git diff --check`
  passed. Stale-provider/API inspection includes `launch/`; no active runtime
  or operator instructions use the old provider/API.

Mandatory separate SDK acceptance/CI command (default pytest skips it):

```bash
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" \
  .venv-speech/bin/python -m pytest -q test/test_speech_sdk.py --run-speech-sdk
```

The flag fails if SDK 2.33.x is absent or incompatible. Omitting it leaves the
SDK contract untested. Generate Content is the Python 3.10-compatible ruling;
a later Interactions migration needs a ROS/Python upgrade and fresh SDK proof.

Environment concern: the pre-existing speech venv's NumPy 1.26.4 exposes
`test_extreme_out_of_bounds_vertices_do_not_overflow_opencv` at
`region_validation.py:86` (overflow converting 1e100 to float32). The same
unchanged test passes with the portable ROS environment's NumPy 1.21.5.
No geometry code or NumPy version was changed in this speech fix. A full run
inside the speech venv therefore remains affected; it is not represented by
the green portable ROS suite or the separate speech SDK acceptance.

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
