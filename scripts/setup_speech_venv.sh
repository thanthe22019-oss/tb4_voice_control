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
import os

import google.genai
import sounddevice

print('Speech environment imports: OK')
for distribution in ('google-genai', 'numpy', 'sounddevice'):
    print(f'{distribution}=={version(distribution)}')
print(f"GEMINI_API_KEY: {'present' if os.environ.get('GEMINI_API_KEY', '').strip() else 'absent'}")

try:
    device = sounddevice.query_devices(kind='input')
except Exception as error:
    print(f'Microphone preflight: unavailable ({error})')
else:
    print(f"Microphone preflight: {device['name']}")
PY

echo
echo 'Gemini launcher (requires Internet, quota, and a built ROS workspace):'
echo "  \"$REPO_ROOT/scripts/run_voice_control.sh\""
