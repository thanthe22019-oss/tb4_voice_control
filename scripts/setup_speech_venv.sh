#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"
VENV_PATH="$REPO_ROOT/.venv-speech"
REQUIREMENTS_PATH="$REPO_ROOT/requirements-speech.txt"

python3 -m venv --system-site-packages "$VENV_PATH"
"$VENV_PATH/bin/python" -m pip install --upgrade pip
"$VENV_PATH/bin/python" -m pip install -r "$REQUIREMENTS_PATH"
"$VENV_PATH/bin/python" -m pip check

"$VENV_PATH/bin/python" - <<'PY'
from importlib.metadata import version

import sounddevice
import faster_whisper

print('Speech environment imports: OK')
for distribution in ('faster-whisper', 'ctranslate2', 'sounddevice'):
    print(f'{distribution}=={version(distribution)}')

try:
    device = sounddevice.query_devices(kind='input')
except Exception as error:
    print(f'Microphone preflight: unavailable ({error})')
else:
    print(f"Microphone preflight: {device['name']}")
PY

echo
echo 'CUDA preflight (requires an NVIDIA driver and may download model small):'
echo "  $VENV_PATH/bin/python -c 'from faster_whisper import WhisperModel; WhisperModel(\"small\", device=\"cuda\", compute_type=\"float16\"); print(\"CUDA Whisper: OK\")'"
