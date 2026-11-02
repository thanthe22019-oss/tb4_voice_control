#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"
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
VENV_SITE="$($VENV_PATH/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
export PYTHONPATH="$VENV_SITE${PYTHONPATH:+:$PYTHONPATH}"
export HF_HOME="${HF_HOME:-$REPO_ROOT/.speech-model-cache}"

# NVIDIA wheel installations keep runtime libraries below site-packages.
NVIDIA_LIBRARY_PATHS=()
for library_path in "$VENV_SITE"/nvidia/*/lib; do
    if [[ -d "$library_path" ]]; then
        NVIDIA_LIBRARY_PATHS+=("$library_path")
    fi
done
if (( ${#NVIDIA_LIBRARY_PATHS[@]} )); then
    NVIDIA_LIBRARY_PATH="$(IFS=:; echo "${NVIDIA_LIBRARY_PATHS[*]}")"
    export LD_LIBRARY_PATH="$NVIDIA_LIBRARY_PATH${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

exec ros2 run tb4_voice_control voice_control "$@"
