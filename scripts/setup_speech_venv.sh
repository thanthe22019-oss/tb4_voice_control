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
echo 'CUDA preflight (requires an NVIDIA driver and a built ROS workspace):'
echo '  nvidia-smi'
echo "  \"$REPO_ROOT/scripts/run_voice_control.sh\""
echo 'The launcher prepends venv site-packages/nvidia/*/lib to LD_LIBRARY_PATH.'
echo 'Use push-to-talk for the first transcription to check CUDA inference.'
echo 'Model small downloads on first transcription; opening the UI alone does not check CUDA.'
