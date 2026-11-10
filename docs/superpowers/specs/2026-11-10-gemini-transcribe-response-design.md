# Gemini Transcribe Response Design

## Intent

Make the existing Gemini-only push-to-talk path use the dedicated speech-to-text
model that responded successfully in the live diagnostic, without changing the
ROS, Qt, audio-capture, command-parsing, or Nav2 boundaries.

## Evidence

- The exact valid `/tmp/tb4-mic.wav` request to `gemini-3.8-flash` reached the
  Gemini service but ended with HTTP 504 after roughly 107 seconds.
- With the same production request shape and a newly supplied credential,
  `gemini-3.5-transcribe` returned in roughly 3.2 seconds.
- The successful response contained an SDK `Part.audio_transcription` payload
  instead of a normal text part. The current adapter only reads
  `response.text`, so it classified that valid response as malformed.
- The installed `google-genai==2.33.0` exposes `Part.audio_transcription` and
  `Transcription.text`, so no dependency or Python upgrade is required.

## Goals

- Select `gemini-3.5-transcribe` by default in source and shipped YAML.
- Extract ordered `audio_transcription.text` values from the first candidate.
- Preserve `response.text` support for injected clients and compatible Gemini
  responses.
- Treat HTTP 504 as an actionable transcription timeout.
- Prove the response contract with unit tests and the real SDK over an offline
  mock transport before any further live audio request.

## Non-goals

- No migration to the Interactions API or Gemini Live API.
- No local NVIDIA/GPU speech inference and no fallback provider.
- No changes to microphone capture, Vietnamese command parsing, semantic map,
  Qt layout, ROS nodes, or Nav2 behavior.
- No automatic retry; one press continues to produce one inference request.

## Approaches

1. **Dedicated Transcribe model with dual response parsing — selected.** Read
   `audio_transcription.text` first and fall back to `response.text`. This is the
   smallest change supported by the live evidence and keeps existing test
   seams compatible.
2. **Keep `gemini-3.8-flash` and extend timeout/retry — rejected.** The exact
   WAV already reproduced a backend deadline at 120 seconds; retrying would
   increase latency and quota without addressing the failing model path.
3. **Migrate to Interactions/Live transcription — deferred.** This is a larger
   transport and lifecycle change that is unnecessary for recorded
   push-to-talk commands and would expand the current milestone.

## Response contract

The adapter examines `response.candidates[0].content.parts` in order. Every
string `part.audio_transcription.text`, including an empty string, is a valid
transcription segment. Multiple non-empty segments are normalized and joined
with a single space. If no specialized segment exists, a string
`response.text` remains valid. Any other shape raises the existing sanitized
`SpeechModelError` and does not leak provider response details.

## Acceptance

- A specialized transcription response returns the existing
  `TranscriptionResult` contract.
- Plain text and empty plain-text responses remain supported.
- Missing or non-string outputs still raise a typed malformed-response error.
- HTTP 504 produces the timeout category in both unit and actual-SDK offline
  acceptance tests.
- Default config, UI status model, README, and handoff status agree on
  `gemini-3.5-transcribe`.
- Full pytest, explicit SDK acceptance, colcon build/test/result, formatting,
  and secret scans pass without a live credential.

