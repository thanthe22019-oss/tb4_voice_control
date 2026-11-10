# TB4 Voice Control — Recovery Handoff

Updated 2026-11-10 (Asia/Ho_Chi_Minh). Active checkout:
`/home/alex/Interaction/tb4_voice_control/.worktrees/gemini-transcribe-response`,
branch `fix/gemini-transcribe-response`. The completed
`feature/implementation` history was fast-forwarded into `main` through
`5a34721`; the post-merge clean-setup fix is `5364aff`. Base/bootstrap commit:
`3161f4d`; Gemini migration reviewed range: `d53fc62..bb5e637`; SDK
compatibility implementation: `d71307e`.
The original `tb4_nav2` source remains unchanged.

The automated Gemini integration and offline SDK acceptance are complete locally:
push-to-talk uses the Generate Content API on `google-genai>=2.33,<2.34`,
configured through `config/voice.yaml`; setup and launcher use a
separate speech venv and the `GEMINI_API_KEY` environment variable. The UI,
semantic regions, parser, route executor and Nav2 cleanup lifecycle are retained.
Speech audio is sent to Google, requiring Internet and quota. Never record a key
in this file or commit one.

## Fresh dedicated-model offline verification

On 2026-11-10, in the isolated fix worktree after `80aeed5`, the default is
`gemini-3.5-transcribe`. The adapter decodes ordered
`audio_transcription.text` segments from the first candidate, keeps the
plain `response.text` fallback, and categorizes HTTP 504 as timeout.

- Speech unit tests: 33 passed. The new 504 case first failed with the
  generic transcription error, then passed after the timeout mapping.
- Explicit actual-SDK acceptance: 11 passed using the speech venv and
  synthetic key + MockTransport only. The 504 case also failed before the
  mapping; each transport case enforces one request and no retry wait.
- Full pytest with ROS Humble sourced: 317 passed, 12 skipped,
  2 inherited SelectableGroups deprecation warnings. Skips are the existing
  copyright check plus 11 opt-in SDK tests.
- Colcon build and test each finished 1 package. Colcon pytest: 317 passed,
  12 skipped, 2 inherited warnings; `colcon test-result --verbose` reported
  329 tests, 0 errors, 0 failures, 12 skipped. Package stderr contained the
  same deprecation warnings.
- `git diff --check` passed. The plan's original secret-scan expression
  matched only its own documented command; a corrected literal credential
  prefix scan found zero matching files. No real key, captured audio or
  live API request was used for this verification.

## Historical post-merge offline verification

On 2026-11-10, on `main` after `86e82d7`, with ROS Humble sourced and Qt
offscreen:

- Explicit actual-SDK acceptance: 9 passed with Python 3.10.12 and
  google-genai 2.33.0 in the newly created main-checkout `.venv-speech`.
  Synthetic key + MockTransport only; no billed Gemini request was made.
- Full portable ROS pytest: 309 passed, 10 skipped, 2 inherited deprecation
  warnings. Skips are the existing copyright check plus 9 opt-in SDK tests.
- The full portable suite run through `.venv-speech/bin/python` with ROS sourced
  also passed 309 tests with the same 10 skips and 2 warnings.
- Colcon build: 1 package finished. Colcon test: 309 passed, 10 skipped,
  2 inherited warnings. Test result: 319 tests, 0 errors, 0 failures,
  10 skipped; one package emitted the same warnings on stderr.
- Speech setup completed with google-genai 2.33.0, NumPy 1.21.5,
  sounddevice 0.5.6 and the default input device detected. The setup now
  validates its own imports/versions without allowing an unrelated broken
  Ubuntu system package to abort the isolated speech setup. Bash syntax and
  `git diff --check` passed.

Mandatory separate SDK acceptance/CI command (default pytest skips it):

```bash
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" \
  ../../.venv-speech/bin/python -m pytest -q test/test_speech_sdk.py --run-speech-sdk
```

The flag fails if SDK 2.33.x is absent or incompatible. Omitting it leaves the
SDK contract untested. Generate Content is the Python 3.10-compatible ruling;
a later Interactions migration needs a ROS/Python upgrade and fresh SDK proof.

## Pending acceptance and publication

- Live credential diagnostics on 2026-11-10 used keys only through transient
  process input and did not persist them. Model metadata/catalog access worked,
  but the original 30-second inference deadline repeatedly returned HTTP 504.
  With a 120-second deadline, both text generation and the production inline-WAV
  adapter completed on `gemini-3.8-flash`; the shipped timeout was therefore
  raised to 120 seconds. The 0.5-second WAV contained silence and still produced
  non-empty text, so this proves connectivity only, not recognition accuracy.
  Both keys pasted into chat must be revoked/rotated.
- A later diagnostic using the captured WAV and the production request shape
  reached HTTP 504 on `gemini-3.8-flash` after roughly 107 seconds.
  `gemini-3.5-transcribe` returned in roughly 3.2 seconds with a specialized
  `audio_transcription` payload. The old adapter read only `response.text`
  and reported this valid response as malformed; the dedicated-model fix
  now decodes that payload. This response alone does not establish Vietnamese
  transcript accuracy.
- The ROS/TurtleBot 4 launch tree, RViz, Gazebo server/gui and separate Voice
  Control runner were shut down before implementation. SIGINT/SIGTERM stopped
  the launch and simulator processes; the final Voice Control child required
  SIGKILL. A host process check returned `NO_RELATED_PROCESSES`; no files or
  data were removed.
- Vietnamese transcript accuracy for the three commands and live TurtleBot
  4/Nav2 acceptance remain pending until the UI is relaunched with a fresh
  restricted key. Unknown-region UI error and absence of a Nav2 goal also
  require live evidence. See `docs/TEST_MATRIX.md`.
- GitHub publication and video remain pending; no public remote is verified.
- The academic HTML/PDF report remains deferred and outside this milestone.

Historical CUDA and microphone runs, plans and reviews are evidence of the old
provider only and do not establish current Gemini acceptance. Their details
remain in repository history and the explicitly marked historical plans/specs.
The earlier runtime implementation is merged locally; the dedicated-model fix
is still on the isolated branch for review and integration. Do not publish
without the user's GitHub authentication/remote choice.

## Resume

Inspect `git status`, source `/opt/ros/humble/setup.bash`, and follow README for
build, setup and operator workflow. Preserve existing changes. Re-run the full
pytest and colcon proof after changes; update this file with fresh evidence.
