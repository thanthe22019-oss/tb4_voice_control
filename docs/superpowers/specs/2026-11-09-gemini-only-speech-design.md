# Gemini-Only Speech Design

## Intent

Replace local Faster-Whisper/CUDA inference with Gemini API transcription while
preserving the existing push-to-talk, command parser, and Nav2 lifecycle. The
robot operator should press record, speak a short Vietnamese navigation command,
and receive text through the same runtime-controller path as typed input.

## Goals

- Keep `AudioRecorder` and `SpeechWorker` as the microphone/thread boundary.
- Replace `WhisperTranscriber` with `GeminiTranscriber` behind the existing
  `transcribe(samples, sample_rate) -> TranscriptionResult` contract.
- Send short recordings as inline WAV audio; never persist recordings locally.
- Read credentials only from `GEMINI_API_KEY` (or SDK-supported environment),
  never YAML, logs, Git, or exception messages.
- Fail with actionable typed errors for a missing key, timeout, quota/auth,
  malformed response, or network outage.
- Remove runtime use of Faster-Whisper, CTranslate2, cuBLAS, cuDNN, and the GPU.

## Non-goals

- Offline transcription or a local fallback.
- Gemini Live/WebSocket streaming; the interaction remains push-to-talk.
- Sending navigation actions directly from Gemini. Gemini produces text only;
  the deterministic command parser remains authoritative.
- Storing audio in the Gemini Files API or on local disk.
- Solving live TurtleBot/Nav2 simulator acceptance in this change.

## Architecture

### Audio request

`GeminiTranscriber` accepts the existing contiguous mono float32 NumPy array.
It clamps samples to `[-1, 1]`, converts them to signed 16-bit PCM, and writes a
mono WAV into `io.BytesIO` with the supplied sample rate. A maximum 15-second
16 kHz clip is about 480 KB and remains comfortably below Gemini's documented
20 MB inline-request limit.

The adapter base64-encodes the WAV and sends one Interactions API request using
the official `google-genai` SDK:

- configurable model, with a documented default suitable for audio input;
- text instruction requesting only the exact Vietnamese navigation utterance,
  an empty response when speech is unintelligible, and no explanation;
- inline `audio/wav` input;
- `store=False`;
- a bounded configurable timeout.

There is no automatic retry. A retry after an ambiguous timeout could duplicate
cost and feed a stale command to the robot; the operator can press record again.

### Configuration and secrets

`config/voice.yaml` contains only non-secret settings:

- `provider: gemini`
- `model`
- `language: vi`
- `request_timeout_seconds`
- existing sample rate and maximum recording duration.

`GEMINI_API_KEY` is supplied by the process environment. Startup/preflight
checks report only whether it is present, never its value. `run_voice_control.sh`
no longer configures NVIDIA library paths and produces an actionable error when
the key is absent.

### Dependencies and migration

`requirements-speech.txt` replaces Faster-Whisper and NVIDIA runtime wheels with
a bounded `google-genai` dependency while retaining `numpy<2` for Ubuntu 22.04
ROS/OpenCV ABI compatibility and `sounddevice` for capture. The setup script
prints resolved Gemini SDK and audio dependency versions plus key-presence and
microphone preflight results.

Existing `.venv-speech` environments may retain unused NVIDIA wheels after an
in-place install. Documentation provides a safe explicit recreation command for
operators who want to reclaim disk; runtime correctness must not depend on
uninstalling those extras.

### Errors and UI

Keep `SpeechModelError` as the typed speech-service boundary for compatibility,
but messages refer to Gemini/API rather than model/GPU. The Qt worker continues
to emit an error without passing text to navigation. The window status changes
from a GPU label to `Gemini API — <model>`.

Gemini never selects a region or sends a Nav2 goal. Its returned text travels
through `RuntimeController.process_text`, so unknown/ambiguous regions retain
the existing deterministic handling.

## Security and privacy

- Never commit or print API keys.
- Do not include audio bytes, request headers, or raw SDK response objects in
  exceptions/logs.
- Use inline audio with `store=False`; no local temporary file and no Files API
  upload lifecycle.
- README states that microphone audio is sent to Google and Internet/API quota
  are required.

## Testing

All automated tests use an injected fake Gemini client; they make no network,
microphone, or GPU calls. Tests cover WAV format/clipping, inline MIME/base64,
model/timeout/store parameters, exact text extraction, empty/malformed output,
missing credentials, sanitized API failures, configuration, dependency removal,
launcher key checks, and unchanged worker/controller routing.

Manual acceptance requires a real restricted Gemini API key in the environment
and three Vietnamese command recordings. It records latency and transcript
accuracy but never the key.

## Success criteria

- No production import or execution path references Faster-Whisper/CTranslate2
  or NVIDIA CUDA libraries.
- The full automated and colcon suites pass without network or hardware.
- With `GEMINI_API_KEY` set, three target commands transcribe into text accepted
  by the existing parser; without the key or network, no navigation goal is sent
  and the UI reports an actionable error.
