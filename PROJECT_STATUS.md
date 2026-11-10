# TB4 Voice Control — Recovery Handoff

Updated 2026-11-10 (Asia/Ho_Chi_Minh). Active checkout:
`/home/alex/Interaction/tb4_voice_control`, branch `main`. The completed
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

## Fresh post-merge offline verification

On 2026-11-10, on `main` after `5364aff`, with ROS Humble sourced and Qt
offscreen:

- Explicit actual-SDK acceptance: 9 passed with Python 3.10.12 and
  google-genai 2.33.0 in the newly created main-checkout `.venv-speech`.
  Synthetic key + MockTransport only; no billed Gemini request was made.
- Full portable ROS pytest: 308 passed, 10 skipped, 2 inherited deprecation
  warnings. Skips are the existing copyright check plus 9 opt-in SDK tests.
- The full portable suite run through `.venv-speech/bin/python` with ROS sourced
  also passed 308 tests with the same 10 skips and 2 warnings.
- Colcon build: 1 package finished. Colcon test: 308 passed, 10 skipped,
  2 inherited warnings. Test result: 318 tests, 0 errors, 0 failures,
  10 skipped; one package emitted the same warnings on stderr.
- Speech setup completed with google-genai 2.33.0, NumPy 1.21.5,
  sounddevice 0.5.6 and the default input device detected. The setup now
  validates its own imports/versions without allowing an unrelated broken
  Ubuntu system package to abort the isolated speech setup. Bash syntax and
  `git diff --check` passed.

Mandatory separate SDK acceptance/CI command (default pytest skips it):

```bash
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" \
  .venv-speech/bin/python -m pytest -q test/test_speech_sdk.py --run-speech-sdk
```

The flag fails if SDK 2.33.x is absent or incompatible. Omitting it leaves the
SDK contract untested. Generate Content is the Python 3.10-compatible ruling;
a later Interactions migration needs a ROS/Python upgrade and fresh SDK proof.

## Pending acceptance and publication

- Live credential diagnostic on 2026-11-10 used the key only through transient
  process input and did not persist it. Model metadata/catalog access succeeded,
  but `generateContent` did not: the configured model and the catalog's latest
  Flash alias returned HTTP 504, while `gemini-2.5-flash` returned HTTP 404.
  No live transcript was produced, so this is failure evidence rather than
  acceptance. Re-test with a newly rotated/restricted key and a provider-confirmed
  inference model before changing the matrix status.
- Real-key Gemini transcription of the three Vietnamese commands, including
  correctness and latency, remains pending. Unknown-region UI error and absence
  of a Nav2 goal also require live evidence. See `docs/TEST_MATRIX.md`.
- Live TurtleBot 4/Nav2 simulation acceptance remains pending.
- GitHub publication and video remain pending; no public remote is verified.
- The academic HTML/PDF report remains deferred and outside this milestone.

Historical CUDA and microphone runs, plans and reviews are evidence of the old
provider only and do not establish current Gemini acceptance. Their details
remain in repository history and the explicitly marked historical plans/specs.
The implementation is merged locally; do not publish without the user's
GitHub authentication/remote choice.

## Resume

Inspect `git status`, source `/opt/ros/humble/setup.bash`, and follow README for
build, setup and operator workflow. Preserve existing changes. Re-run the full
pytest and colcon proof after changes; update this file with fresh evidence.
