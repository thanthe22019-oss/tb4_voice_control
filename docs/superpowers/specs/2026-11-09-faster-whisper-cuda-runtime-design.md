# Faster-Whisper CUDA Runtime Design

## Intent

Make the documented speech setup reproducibly install and launch the CUDA
runtime that Faster-Whisper actually needs on Ubuntu 22.04. The proven target
is the existing NVIDIA RTX 3050 configuration using model `small`, device
`cuda`, and compute type `float16`.

## Goals

- Install the CUDA 12 cuBLAS and cuDNN 9 runtime libraries inside the isolated
  `.venv-speech` environment.
- Keep the existing launcher responsible for adding venv-provided NVIDIA
  library directories to `LD_LIBRARY_PATH` before ROS starts.
- Make setup/preflight output tell the operator how the launcher supplies the
  runtime paths.
- Preserve CPU/system ROS packages through the existing
  `--system-site-packages` venv.

## Non-goals

- Installing the full CUDA Toolkit or changing the NVIDIA driver.
- Committing the venv, model cache, or recorded audio.
- Tuning recognition quality or changing the Whisper model.

## Approaches

1. **NVIDIA pip runtime wheels (selected):** add `nvidia-cublas-cu12` and
   `nvidia-cudnn-cu12` major-version constraints to the speech requirements.
   This is the Faster-Whisper documented Linux method and stays isolated in
   the project venv. The existing launcher already discovers
   `site-packages/nvidia/*/lib`.
2. **System CUDA Toolkit:** works but requires root-managed repositories and a
   much larger host installation; it is unnecessary for this Python runtime.
3. **Manual shared-library archive/symlinks:** fragile and not reproducible;
   rejected.

## Constraints

- `faster-whisper>=1.1.0,<2.0` and `ctranslate2` remain the speech engine.
- CUDA runtime dependency majors are CUDA 12 for cuBLAS and cuDNN 9.
- `run_voice_control.sh` must preserve an existing `LD_LIBRARY_PATH` after
  prepending venv NVIDIA library directories.
- Tests must prove dependency declarations and launcher/preflight behavior
  without downloading packages, models, or requiring a GPU.

## Success

Automated tests pass, the speech setup declares the required runtime wheels,
and the same launcher environment supports a real microphone capture followed
by a CUDA `float16` transcription.
