# Faster-Whisper CUDA Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the isolated speech setup install and launch the CUDA runtime required by Faster-Whisper on Linux.

**Architecture:** Keep CUDA user-space libraries inside `.venv-speech` through NVIDIA pip wheels. Preserve the existing launcher discovery of `site-packages/nvidia/*/lib`, and align setup guidance and README with that runtime contract.

**Tech Stack:** Bash, Python 3.10 venv, Faster-Whisper, CTranslate2, NVIDIA CUDA 12 cuBLAS, cuDNN 9, pytest.

**Spec:** `docs/superpowers/specs/2026-11-09-faster-whisper-cuda-runtime-design.md`

## Global Constraints

- Keep `faster-whisper>=1.1.0,<2.0` and the isolated `--system-site-packages` speech venv.
- Declare CUDA 12 cuBLAS and cuDNN 9 runtime wheels with major-version upper bounds.
- Preserve any existing `LD_LIBRARY_PATH` after prepending venv NVIDIA library directories.
- Tests may not download packages/models or require GPU/microphone hardware.
- Do not commit `.venv-speech`, `.speech-model-cache`, or audio recordings.

## Review Focus

- Fresh speech setup must install both NVIDIA runtime wheel families.
- A venv path containing spaces must remain correctly quoted.
- Multiple discovered NVIDIA `lib` directories must be colon-separated and prepended to an existing `LD_LIBRARY_PATH`.
- A CPU-only or incomplete venv with no NVIDIA library directories must still reach the existing ROS launch path without an empty-path entry.
- Operator guidance must not advertise a CUDA preflight command that omits the launcher-managed library path.

---

### Task 1: Reproducible Faster-Whisper CUDA runtime

**Files:**
- Modify: `requirements-speech.txt`
- Modify: `scripts/setup_speech_venv.sh`
- Modify: `README.md`
- Test: `test/test_install_assets.py`

**Interfaces:**
- Consumes: existing `.venv-speech` setup and `scripts/run_voice_control.sh` NVIDIA library discovery.
- Produces: speech requirements containing CUDA 12 cuBLAS and cuDNN 9; setup/README guidance that routes CUDA preflight through the launcher-managed environment.

- [ ] **Step 1: Write failing delivery tests**

Add tests that parse `requirements-speech.txt` and require `nvidia-cublas-cu12` constrained below 13 plus `nvidia-cudnn-cu12` constrained to major 9. Add a setup-guidance assertion that the printed CUDA preflight explicitly uses the same venv NVIDIA library discovery contract as the launcher, rather than a bare Python command.

- [ ] **Step 2: Run tests to verify RED**

Run: `PYTHONPATH="$PWD:$PYTHONPATH" pytest -q test/test_install_assets.py -k "cuda_runtime or cuda_preflight"`

Expected: FAIL because requirements omit both NVIDIA runtime packages and setup prints a bare Python preflight.

- [ ] **Step 3: Implement the minimal runtime declaration and guidance**

Add `nvidia-cublas-cu12>=12,<13` and `nvidia-cudnn-cu12>=9,<10` to `requirements-speech.txt`. Update setup output and README so operators use `scripts/run_voice_control.sh` (which already prepends venv NVIDIA libraries) and explain that model download occurs on first transcription. Do not install the full CUDA Toolkit or duplicate launcher path logic in Python.

- [ ] **Step 4: Run focused and full verification**

Run:

```bash
source /opt/ros/humble/setup.bash
PYTHONPATH="$PWD:$PYTHONPATH" pytest -q test/test_install_assets.py
QT_QPA_PLATFORM=offscreen PYTHONPATH="$PWD:$PYTHONPATH" pytest -q
```

Expected: focused and full suites pass with only the inherited skip/warnings.

- [ ] **Step 5: Update recovery evidence and commit**

Update `PROJECT_STATUS.md` with the end-to-end microphone/CUDA inference evidence and remaining recognition-quality/live-simulator work. Commit source, tests, docs, and handoff with message `fix: install Faster-Whisper CUDA runtime`.
