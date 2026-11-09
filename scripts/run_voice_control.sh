#!/usr/bin/env bash
set -euo pipefail

if [[ ! "${GEMINI_API_KEY:-}" =~ [^[:space:]] ]]; then
    echo 'Gemini API key is required. Run: export GEMINI_API_KEY="your-api-key"' >&2
    exit 1
fi

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
SOURCE_CANDIDATE="$(cd "$SCRIPT_DIR/.." && pwd)"
if [[ -f "$SOURCE_CANDIDATE/setup.py" ]]; then
    REPO_ROOT="$SOURCE_CANDIDATE"
else
    PACKAGE_PREFIX="$(cd "$SCRIPT_DIR/../../.." && pwd)"
    if [[ "$(basename "$PACKAGE_PREFIX")" == "tb4_voice_control" ]]; then
        DEFAULT_REPO_ROOT="$(cd "$PACKAGE_PREFIX/../.." && pwd)"
    else
        DEFAULT_REPO_ROOT="$(cd "$PACKAGE_PREFIX/.." && pwd)"
    fi
    REPO_ROOT="${TB4_VOICE_CONTROL_ROOT:-$DEFAULT_REPO_ROOT}"
fi
ROS_SETUP="${ROS_SETUP:-/opt/ros/humble/setup.bash}"
WORKSPACE_SETUP="$REPO_ROOT/install/setup.bash"
VENV_PATH="$REPO_ROOT/.venv-speech"

if [[ ! -f "$ROS_SETUP" ]]; then
    echo "ROS setup not found: $ROS_SETUP" >&2
    exit 1
fi
if [[ ! -f "$WORKSPACE_SETUP" ]]; then
    echo "Workspace is not built: $WORKSPACE_SETUP" >&2
    echo "Run: cd $REPO_ROOT && colcon build --symlink-install" >&2
    exit 1
fi
if [[ ! -f "$VENV_PATH/bin/activate" ]]; then
    echo "Speech environment not found: $VENV_PATH" >&2
    echo "Run: $REPO_ROOT/scripts/setup_speech_venv.sh" >&2
    exit 1
fi

# ROS setup scripts may read unset environment variables.
set +u
source "$ROS_SETUP"
source "$WORKSPACE_SETUP"
source "$VENV_PATH/bin/activate"
set -u

# Installed ROS console scripts can retain a system-Python shebang. Expose the
# venv packages explicitly so the speech dependencies remain importable.
VENV_SITE="$("$VENV_PATH/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
export PYTHONPATH="$VENV_SITE${PYTHONPATH:+:$PYTHONPATH}"

exec ros2 run tb4_voice_control voice_control "$@"
