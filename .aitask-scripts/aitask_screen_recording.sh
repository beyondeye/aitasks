#!/usr/bin/env bash
set -euo pipefail

# aitask_screen_recording.sh - Turn a screen recording into frames, contact
# sheets, a timeline and animation timing data an agent can read (Claude Code
# cannot open video files). Backs the aitask-screen-recording skill.
#
# Usage: ./.aitask-scripts/aitask_screen_recording.sh info|bug|anim VIDEO [options]
#        ./.aitask-scripts/aitask_screen_recording.sh <mode> --help
#
# Needs ffmpeg/ffprobe >= 5.1 on PATH. ImageMagick 7 (`magick`) is optional:
# without it there are no contact sheets or plots, only frames and data.
# Python stdlib only — runs on the framework venv interpreter.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

exec "$PYTHON" "$SCRIPT_DIR/screen_recording/video_prep.py" "$@"
