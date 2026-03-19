#!/usr/bin/env bash
# aitask_brainstorm_status.sh - Show brainstorm session status or list all sessions.
#
# Usage:
#   ait brainstorm status <task_num>    Show session details
#   ait brainstorm status --list        List all sessions
#   ait brainstorm list                 (alias for --list)
#
# Output: YAML-formatted session details or table of sessions.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Python setup ---
VENV_PYTHON="$HOME/.aitask/venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
    if ! command -v "$PYTHON" &>/dev/null; then
        die "Python not found. Run 'ait setup' to install dependencies."
    fi
    if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
        die "Missing Python package: pyyaml. Run 'ait setup' or: pip install pyyaml"
    fi
fi

# --- Usage ---
show_help() {
    cat <<'HELP'
Usage: ait brainstorm status <task_num>
       ait brainstorm status --list
       ait brainstorm list

Show brainstorm session details or list all sessions.

Arguments:
  <task_num>    Task number to show status for
  --list        List all brainstorm sessions

Example:
  ait brainstorm status 42
  ait brainstorm list
HELP
}

# --- Argument parsing ---
LIST_MODE=false
TASK_NUM=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --list)
            LIST_MODE=true; shift ;;
        --help|-h)
            show_help; exit 0 ;;
        -*)
            die "Unknown option: $1. Run 'ait brainstorm status --help' for usage." ;;
        *)
            if [[ -z "$TASK_NUM" ]]; then
                TASK_NUM="$1"; shift
            else
                die "Unexpected argument: $1"
            fi
            ;;
    esac
done

if $LIST_MODE; then
    exec "$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" list
fi

if [[ -z "$TASK_NUM" ]]; then
    die "Missing <task_num> or --list. Run 'ait brainstorm status --help' for usage."
fi

exec "$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" status --task-num "$TASK_NUM"
