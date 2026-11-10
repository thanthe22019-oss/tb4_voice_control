# Gemini Transcribe Response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Gemini-only voice runtime consume the fast dedicated transcription response and report provider deadlines accurately.

**Architecture:** Keep the existing Generate Content request boundary and add one SDK-independent response normalizer inside `speech.py`. Select the dedicated model consistently through defaults and YAML, while preserving plain-text response compatibility and the one-request/no-retry behavior.

**Tech Stack:** Python 3.10, ROS 2 Humble, PyQt5, `google-genai==2.33.x`, NumPy, pytest, colcon

**Spec:** `docs/superpowers/specs/2026-11-10-gemini-transcribe-response-design.md`

## Global Constraints

- Gemini is the only speech provider; do not add local GPU or another API fallback.
- Keep Python 3.10 and `google-genai>=2.33,<2.34` compatibility.
- Keep inline mono PCM16 WAV, `store=False`, `automatic_continuation=False`, 120-second deadline, and no automatic retry.
- Never persist, print, test with, or commit a real API key or captured voice file.
- Preserve the existing `TranscriptionResult` and `SpeechModelError` public contracts.

## Review Focus

- Specialized output contains one empty-string transcript: accept it as a valid empty command rather than malformed output (Task 1).
- Specialized output contains multiple ordered segments: normalize and join them without changing their order (Task 1).
- Specialized output is absent but `response.text` is a string: retain the existing fallback behavior (Task 1).
- Candidate/content/part attributes are absent or transcription text is non-string: raise the sanitized malformed-response error (Task 1).
- Provider wraps HTTP 504 in an SDK server error: categorize it as timeout without leaking the response body or key (Task 2).

---

### Task 1: Dedicated model and response contract

**Files:**
- Modify: `test/test_speech.py:15-140`
- Modify: `test/test_speech_sdk.py:45-83`
- Modify: `test/test_install_assets.py:24-31`
- Modify: `test/test_voice_app.py:80-185`
- Modify: `tb4_voice_control/speech.py:65-127`
- Modify: `tb4_voice_control/voice_app.py:340-365`
- Modify: `config/voice.yaml:1-6`

**Interfaces:**
- Consumes: existing `GeminiTranscriber.transcribe(samples, sample_rate) -> TranscriptionResult` and Generate Content response objects.
- Produces: `_transcription_text(response: Any) -> str | None`; `GeminiTranscriber(model: str = 'gemini-3.5-transcribe', ...)`; shipped model `gemini-3.5-transcribe`.

- [ ] **Step 1: Write failing unit and actual-SDK tests for the specialized response**

  Add tests named `test_audio_transcription_parts_return_existing_result_contract`, `test_audio_transcription_parts_preserve_order`, and `test_empty_audio_transcription_is_valid`. Construct SDK-shaped namespaces under `candidates[0].content.parts[*].audio_transcription.text`; assert stripped text, ordered single-space joining, and valid empty `TranscriptionResult` respectively. Add a malformed-response case whose specialized text is non-string. Keep the existing plain `response.text` test as fallback proof. In `test/test_speech_sdk.py`, add `test_real_sdk_decodes_audio_transcription_part` whose mock HTTP JSON contains `candidates[0].content.parts[0].audioTranscription.text`; assert the production adapter returns the existing `TranscriptionResult` and makes exactly one request.

- [ ] **Step 2: Write failing default-model tests**

  Change assertions in `test_request_is_stateless_bounded_and_has_no_continuation`, `test_real_sdk_accepts_inline_wav_and_stateless_config`, `test_voice_config_uses_only_gemini_settings`, and the UI fake/status test from `gemini-3.8-flash` to `gemini-3.5-transcribe`.

- [ ] **Step 3: Run the focused tests and verify RED**

  Run: `PYTHONPATH="$PWD" pytest -q test/test_speech.py test/test_install_assets.py::test_voice_config_uses_only_gemini_settings test/test_voice_app.py::test_window_shows_runtime_context_and_push_to_talk_pipeline`

  Run: `PYTHONPATH="$PWD" .venv-speech/bin/python -m pytest -q test/test_speech_sdk.py --run-speech-sdk`

  Expected: both commands FAIL because specialized responses are reported as malformed and defaults still resolve to `gemini-3.8-flash`.

- [ ] **Step 4: Implement `_transcription_text(response: Any) -> str | None`**

  In `speech.py`, traverse only the first candidate's ordered content parts, collect every string `audio_transcription.text`, return their stripped single-space join when at least one string is present, otherwise fall back to a string `response.text`, and return `None` for malformed shapes. Make `transcribe` call this helper before constructing `TranscriptionResult`.

- [ ] **Step 5: Select the dedicated model everywhere**

  Change the defaults in `GeminiTranscriber`, `voice_app.main`, and `config/voice.yaml` to exactly `gemini-3.5-transcribe`. Update the matching offline SDK URL, shipped config, and UI test fixtures/assertions.

- [ ] **Step 6: Run focused unit tests and verify GREEN**

  Run the Step 3 command again.

  Expected: all selected tests PASS with no new warnings.

- [ ] **Step 7: Run explicit SDK acceptance**

  Run: `PYTHONPATH="$PWD" .venv-speech/bin/python -m pytest -q test/test_speech_sdk.py --run-speech-sdk`

  Expected: all SDK acceptance tests PASS without network access or a real key.

- [ ] **Step 8: Commit Task 1**

  Run: `git add tb4_voice_control/speech.py tb4_voice_control/voice_app.py config/voice.yaml test/test_speech.py test/test_speech_sdk.py test/test_install_assets.py test/test_voice_app.py docs/superpowers/specs/2026-11-10-gemini-transcribe-response-design.md docs/superpowers/plans/2026-11-10-gemini-transcribe-response.md && git commit -m "fix: decode Gemini transcription responses"`

### Task 2: Deadline diagnostics and verified handoff

**Files:**
- Modify: `test/test_speech.py:143-180`
- Modify: `test/test_speech_sdk.py:84-112`
- Modify: `tb4_voice_control/speech.py:39-59`
- Modify: `README.md:62-94`
- Modify: `PROJECT_STATUS.md:51-78`

**Interfaces:**
- Consumes from Task 1: dedicated model defaults and `_transcription_text` behavior.
- Produces: `_api_error_message(error)` classifies status 504 as `Speech transcription timeout; try again.`; documentation and resume evidence reflecting the live diagnosis and fresh automated proof.

- [ ] **Step 1: Write failing HTTP 504 tests**

  Add `HttpFailure(504)` with expected category `timeout` to the unit parameterization and add status 504 with expected `timeout` to the actual-SDK mock-transport failure parameterization. Assert the provider sentinel and synthetic key remain absent.

- [ ] **Step 2: Run the focused tests and verify RED**

  Run: `PYTHONPATH="$PWD" pytest -q test/test_speech.py::test_api_failures_are_categorized_without_leaking_details`

  Expected: FAIL because status 504 currently maps to generic `failed`.

- [ ] **Step 3: Implement the minimal 504 mapping**

  In `_api_error_message`, map numeric status 504 through the same timeout message as timeout exception classes, before authentication/rate/network fallbacks.

- [ ] **Step 4: Run unit and actual-SDK focused tests**

  Run: `PYTHONPATH="$PWD" pytest -q test/test_speech.py`

  Run: `PYTHONPATH="$PWD" .venv-speech/bin/python -m pytest -q test/test_speech_sdk.py --run-speech-sdk`

  Expected: both commands PASS; actual SDK makes one mock request per case and performs no retry wait.

- [ ] **Step 5: Update operator documentation and handoff evidence**

  In `README.md`, name `gemini-3.5-transcribe`, explain specialized response decoding, and retain the credential/audio privacy warning. In `PROJECT_STATUS.md`, record the 3.2-second dedicated-model response, the old adapter mismatch, process shutdown, and only verification results actually observed in later steps; state that Vietnamese transcript accuracy and Nav2 live acceptance remain pending until the UI is relaunched with a fresh restricted key.

- [ ] **Step 6: Run the complete proof**

  Run: `PYTHONPATH="$PWD" pytest -q`

  Run: `PYTHONPATH="$PWD" .venv-speech/bin/python -m pytest -q test/test_speech_sdk.py --run-speech-sdk`

  Run: `source /opt/ros/humble/setup.bash && colcon build --symlink-install && colcon test && colcon test-result --verbose`

  Run: `git diff --check`

  Run: `rg -n --hidden --glob '!.git/**' --glob '!.venv-speech/**' 'AQ\\.' .`

  Expected: all test commands PASS, colcon reports zero failures/errors, diff check is empty, and secret scan finds no key literal.

- [ ] **Step 7: Commit Task 2**

  Run: `git add tb4_voice_control/speech.py test/test_speech.py test/test_speech_sdk.py README.md PROJECT_STATUS.md docs/superpowers/specs/2026-11-10-gemini-transcribe-response-design.md docs/superpowers/plans/2026-11-10-gemini-transcribe-response.md && git commit -m "docs: record Gemini transcription proof"`
