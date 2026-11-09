# Gemini-Only Speech Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace local Faster-Whisper/CUDA inference with stateless Gemini API transcription while preserving push-to-talk, deterministic Vietnamese command parsing, and Nav2 routing.

**Architecture:** Keep `AudioRecorder`, `SpeechWorker`, and `RuntimeController` unchanged at their existing boundaries. A new `GeminiTranscriber` converts mono NumPy samples to an in-memory WAV, sends one inline-audio Interactions API request through an injected or lazily constructed Google Gen AI client, and returns the existing `TranscriptionResult`. Runtime configuration, UI, launch scripts, dependencies, and operator documentation become Gemini-only.

**Tech Stack:** Python 3.10, NumPy 1.x ABI, standard-library `wave`/`io`/`base64`, `google-genai`, PyQt5, ROS 2 Humble, pytest/ament.

**Spec:** `docs/superpowers/specs/2026-11-09-gemini-only-speech-design.md`

## Global Constraints

- Speech provider is Gemini-only: no Faster-Whisper, CTranslate2, CUDA, NVIDIA runtime, CPU fallback, Files API, or Live API production path.
- Use `gemini-3.8-flash` as the default configurable audio-capable model and `google-genai>=2.30.1,<3` as the SDK range.
- Read the secret only from `GEMINI_API_KEY`; never place it in YAML, Git, logs, exceptions, test output, or documentation examples containing a real value.
- Send a base64 inline `audio/wav` payload through `client.interactions.create`; set `store=False`, `automatic_continuation=False`, a bounded timeout, and SDK retry attempts to zero.
- The default request timeout is `30` seconds, language is `vi`, recording is mono `16000` Hz with a maximum duration of `15` seconds, and existing `numpy<2`/`sounddevice>=0.4.6,<1.0` constraints remain.
- Gemini returns text only. `RuntimeController.process_text` and the deterministic parser remain solely responsible for selecting regions and sending Nav2 goals.
- Automated tests use injected fakes only and perform no network, microphone, GPU, or Gemini billing operation.
- No local temporary audio file is created; audio exists only in memory for the request.
- API errors must be actionable but sanitized: never include the original exception string, request headers, raw response, audio bytes, or API key.

## Review Focus

- Missing or blank `GEMINI_API_KEY` must raise a typed actionable speech error before importing/constructing the real client; Task 1 pins this in `test_missing_api_key_is_actionable_and_does_not_construct_client`.
- Non-contiguous, multidimensional, or out-of-range samples must become valid clipped mono 16-bit WAV without mutating the caller buffer; Task 1 pins this in `test_request_contains_clipped_mono_pcm16_wav`.
- Empty model text is valid silence, while absent/non-string `output_text` is a malformed response; Task 1 pins both behaviors in `test_empty_output_is_a_valid_transcript` and `test_malformed_output_is_a_typed_error`.
- Timeout, auth, quota, network, and unknown SDK failures must not leak exception text or secrets; Task 1 pins the categories and redaction in `test_api_failures_are_categorized_without_leaking_details`.
- Missing credentials or Gemini failure must emit a UI/runtime error and never enter parser/Nav2 routing; Task 2 pins this with the existing `SpeechWorker` boundary plus `test_speech_error_does_not_send_navigation_goal`.

---

### Task 1: Gemini transcription adapter

**Files:**
- Modify: `tb4_voice_control/speech.py`
- Replace tests: `test/test_speech.py`

**Interfaces:**
- Consumes: mono or reshapeable audio samples accepted by `numpy.asarray`; a positive integer sample rate; optional injected client exposing `interactions.create(**kwargs)`.
- Produces: `GeminiTranscriber(model: str = 'gemini-3.8-flash', language: str = 'vi', request_timeout_seconds: float = 30.0, client: Any | None = None, client_factory: Callable[[str], Any] | None = None)` and its existing-compatible `transcribe(samples: numpy.ndarray, sample_rate: int) -> TranscriptionResult` method.
- Preserves: `SpeechModelError` and `TranscriptionResult(text: str, language: str, duration_seconds: float)` for `SpeechWorker` compatibility.
- Request contract: `client.interactions.create(model=self.model, input=[text_part, audio_part], store=False, automatic_continuation=False, timeout=self.request_timeout_seconds)`, where `audio_part` is `{'type': 'audio', 'data': <base64 WAV string>, 'mime_type': 'audio/wav'}`.
- Default real-client factory: `google.genai.Client(api_key=<environment value>, http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=0)))`; import the optional SDK only when the real client is first needed.
- Text instruction: `Chuyển lời nói tiếng Việt trong audio thành đúng một câu lệnh điều hướng. Chỉ trả về nguyên văn câu lệnh; nếu không nghe rõ, trả về chuỗi rỗng. Không giải thích.`

- [ ] **Step 1: Write the failing request/WAV contract tests**

  Replace Whisper fakes with a fake Interactions client and add `test_request_contains_clipped_mono_pcm16_wav`, `test_request_is_stateless_bounded_and_has_no_continuation`, and `test_valid_output_returns_existing_result_contract`. Decode the captured base64 with `wave.open(io.BytesIO(...))`; assert mono, 16-bit, supplied sample rate, clipped PCM values, exact instruction/audio parts, model `gemini-3.8-flash`, `store is False`, `automatic_continuation is False`, timeout `30.0`, stripped Vietnamese text, language `vi`, and duration `sample_count / sample_rate`.

- [ ] **Step 2: Run the request tests and verify RED**

  Run: `pytest -q test/test_speech.py`

  Expected: FAIL because `GeminiTranscriber` and the Gemini request/WAV behavior do not exist.

- [ ] **Step 3: Implement minimal in-memory WAV and Gemini request behavior**

  In `speech.py`, remove `WhisperTranscriber`, `_faster_whisper_model`, and CUDA model locking. Add `GeminiTranscriber`, private WAV encoding, lazy client creation, and `output_text.strip()` while retaining the existing result/error dataclasses. Validate positive sample rate and positive timeout with `ValueError`.

- [ ] **Step 4: Run the request tests and verify GREEN**

  Run: `pytest -q test/test_speech.py`

  Expected: request/WAV/result tests PASS.

- [ ] **Step 5: Write the failing credential, response, and sanitized-error tests**

  Add `test_missing_api_key_is_actionable_and_does_not_construct_client`, `test_empty_output_is_a_valid_transcript`, `test_malformed_output_is_a_typed_error`, and parameterized `test_api_failures_are_categorized_without_leaking_details`. Cover timeout, HTTP 401/403, HTTP 429, connection/network, and unknown errors; inject a sentinel such as `SECRET_SENTINEL` into each original exception and assert it is absent from `SpeechModelError` text.

- [ ] **Step 6: Run the error tests and verify RED**

  Run: `pytest -q test/test_speech.py`

  Expected: FAIL on the first unimplemented credential/response/error behavior.

- [ ] **Step 7: Implement minimal credential checks and sanitized categorization**

  Accept an injected client without credentials for tests. Otherwise read and strip `GEMINI_API_KEY` immediately before real-client construction; raise a typed setup message when absent. Categorize by safe exception type/status-code inspection only, never `str(error)`, and treat empty string output as a valid transcript but missing/non-string output as malformed.

- [ ] **Step 8: Verify Task 1 and commit**

  Run: `pytest -q test/test_speech.py && git diff --check`

  Expected: all speech tests PASS and no whitespace errors.

  Commit: `feat: add Gemini speech transcription adapter`

---

### Task 2: Runtime configuration and UI integration

**Files:**
- Modify: `tb4_voice_control/voice_app.py`
- Modify: `config/voice.yaml`
- Modify: `scripts/run_voice_control.sh`
- Modify tests: `test/test_voice_app.py`
- Modify tests: `test/test_install_assets.py`

**Interfaces:**
- Consumes from Task 1: `GeminiTranscriber(model, language, request_timeout_seconds)` and unchanged `SpeechModelError`/`TranscriptionResult`.
- Produces config: `provider: gemini`, `model: gemini-3.8-flash`, `language: vi`, `request_timeout_seconds: 30`, `sample_rate: 16000`, `max_record_seconds: 15`.
- Produces UI constructor keyword: `speech_status: str = 'Gemini API chưa kiểm tra'`; the visible row is `Nhận dạng:` and production value is `Gemini API — <model>`.
- Produces launcher behavior: exit `1` with an instruction to export `GEMINI_API_KEY` when the variable is missing/blank; never echo its value; retain ROS/workspace/venv activation and `PYTHONPATH`, but remove `HF_HOME`, NVIDIA library discovery, and `LD_LIBRARY_PATH` mutation.

- [ ] **Step 1: Write failing config and UI integration tests**

  Update the fake transcriber to expose `model = 'gemini-3.8-flash'`. Add tests asserting `voice.yaml` has exactly the Gemini fields/values above and no `model_size`, `device`, or `compute_type`; assert the status row/value says `Gemini API` and contains no CUDA/GPU wording; monkeypatch `GeminiTranscriber` in `main` and assert it receives the configured model/language/timeout while `AudioRecorder` still receives sample rate/duration.

- [ ] **Step 2: Run focused runtime tests and verify RED**

  Run: `QT_QPA_PLATFORM=offscreen pytest -q test/test_voice_app.py test/test_install_assets.py`

  Expected: FAIL because the app imports/constructs Whisper, config is CUDA-based, and the status widget is GPU-specific.

- [ ] **Step 3: Wire `GeminiTranscriber` and Gemini status into the runtime**

  Replace the Whisper import/construction, reject any configured provider other than exact `gemini`, rename the GPU-facing constructor/widget fields to speech-facing names, and construct the production status from `transcriber.model`. Do not change `SpeechWorker` or controller/parser routing.

- [ ] **Step 4: Update `config/voice.yaml` and verify focused GREEN**

  Write only the six non-secret settings in the Interfaces block, then run: `QT_QPA_PLATFORM=offscreen pytest -q test/test_voice_app.py`

  Expected: all voice-app tests PASS.

- [ ] **Step 5: Write failing launcher and no-navigation-on-error tests**

  Add `test_launcher_requires_gemini_key_without_printing_secret` by running the real Bash wrapper with `GEMINI_API_KEY` removed and asserting exit `1`, an actionable variable name, and no sentinel secret. Add `test_launcher_has_no_cuda_runtime_mutation`. Add `test_speech_error_does_not_send_navigation_goal` using a transcriber that raises `SpeechModelError`, and assert the backend receives no region while the UI shows an error.

- [ ] **Step 6: Run the new tests and verify RED**

  Run: `QT_QPA_PLATFORM=offscreen pytest -q test/test_voice_app.py test/test_install_assets.py`

  Expected: FAIL because the wrapper still mutates NVIDIA paths and does not gate startup on the Gemini key.

- [ ] **Step 7: Implement the launcher credential gate and remove CUDA setup**

  Check `GEMINI_API_KEY` before ROS/workspace/venv checks so the diagnostic is deterministic. Keep quoted paths and the installed-source checkout resolution behavior. Remove all local-model cache and NVIDIA runtime setup.

- [ ] **Step 8: Verify Task 2 and commit**

  Run: `QT_QPA_PLATFORM=offscreen pytest -q test/test_voice_app.py test/test_install_assets.py && git diff --check`

  Expected: focused runtime/delivery tests PASS and no whitespace errors.

  Commit: `feat: route voice runtime through Gemini API`

---

### Task 3: Gemini dependency, setup, operator docs, and recovery state

**Files:**
- Modify: `requirements-speech.txt`
- Modify: `scripts/setup_speech_venv.sh`
- Modify: `README.md`
- Modify: `docs/DEMO.md`
- Modify: `docs/TEST_MATRIX.md`
- Modify: `PROJECT_STATUS.md`
- Modify tests: `test/test_install_assets.py`

**Interfaces:**
- Produces dependency set: `google-genai>=2.30.1,<3`, `numpy<2`, and `sounddevice>=0.4.6,<1.0`; no Faster-Whisper/CTranslate2/NVIDIA package.
- Produces setup preflight: print resolved `google-genai`, `numpy`, and `sounddevice` versions, microphone availability, and only whether `GEMINI_API_KEY` is present; never print its value.
- Produces operator workflow: create/recreate `.venv-speech`, export a restricted Gemini API key in the current shell, disclose that microphone audio is sent to Google and requires Internet/quota, run UI, test three Vietnamese commands, and preserve text-input diagnosis.
- Preserves: report generation remains deferred; live Gemini and Nav2 acceptance remain pending until separately evidenced.

- [ ] **Step 1: Write failing dependency/setup/documentation tests**

  Replace CUDA requirement assertions with `test_speech_requirements_are_gemini_only_and_bounded`, checking the exact three packages/ranges and forbidden package absence. Replace the CUDA preflight test with `test_setup_reports_gemini_preflight_without_secret_or_gpu`, checking SDK/audio versions and key-presence wording only. Change the README workflow contract from `nvidia cuda` to `gemini api`, privacy/network/quota, and three voice-command acceptance steps; assert documentation contains no active Faster-Whisper/CUDA setup instructions.

- [ ] **Step 2: Run delivery tests and verify RED**

  Run: `pytest -q test/test_install_assets.py`

  Expected: FAIL because requirements, setup output, and operator docs still describe CUDA/Whisper.

- [ ] **Step 3: Replace speech dependencies and setup preflight**

  Update requirements to the exact Interfaces set. Update the setup script to import `google.genai`, print only safe version/key-presence/device diagnostics, and end with the Gemini launcher command. Do not uninstall extras from an existing venv automatically; document explicit venv recreation for disk cleanup.

- [ ] **Step 4: Rewrite operator and acceptance documentation**

  Update README prerequisites, setup, launch, troubleshooting, privacy, and demo sections; update `docs/DEMO.md` shot preparation/status; update `docs/TEST_MATRIX.md` so Gemini transcription is pending until real-key evidence exists and historical CUDA execution is not presented as current acceptance.

- [ ] **Step 5: Run focused and full automated verification**

  Run:

  ```bash
  source /opt/ros/humble/setup.bash
  QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" pytest -q
  colcon build --base-paths . --packages-select tb4_voice_control --symlink-install
  colcon test --base-paths . --packages-select tb4_voice_control --event-handlers console_direct+
  colcon test-result --verbose
  git diff --check
  rg -n "faster[-_]whisper|ctranslate2|nvidia-cublas|nvidia-cudnn|LD_LIBRARY_PATH|HF_HOME|device: cuda|compute_type" tb4_voice_control config scripts requirements-speech.txt README.md docs test
  ```

  Expected: pytest/colcon report zero failures; `git diff --check` is clean; the final `rg` has no active production/runtime dependency or instruction match (historical evidence may remain only when clearly labeled as historical).

- [ ] **Step 6: Update recovery state with fresh evidence**

  Record exact test counts and current commit range in `PROJECT_STATUS.md`; state that automated Gemini integration is complete, real-key three-command transcription and live Nav2 simulation remain pending, GitHub publication remains pending, and the academic report is still deferred. Never record an API key.

- [ ] **Step 7: Commit Task 3**

  Run: `git status --short`

  Expected: only planned documentation/dependency/setup/status changes are present.

  Commit: `docs: complete Gemini-only speech migration`

## Manual Acceptance After Automated Implementation

This is an external acceptance gate, not an automated subagent test and not a completion prerequisite when no key is available in the process environment.

1. The operator exports a restricted key locally: `export GEMINI_API_KEY='...'` (never paste it into chat or commit it).
2. Recreate or refresh `.venv-speech`, build the workspace, and launch the UI through `scripts/run_voice_control.sh`.
3. Record “Đi đến khu vực A”, “Đi đến phòng thí nghiệm”, and “Di chuyển từ khu vực A đến khu vực B”; record transcript correctness and request latency without capturing the key.
4. Verify an unknown region creates an actionable UI error and no Nav2 goal.
5. Only after those artifacts exist, update `docs/TEST_MATRIX.md` from pending to pass and proceed to the separate live TurtleBot/Nav2 acceptance milestone.
