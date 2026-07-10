#!/usr/bin/env bash
# aitask_chatlink.sh — launcher for the chatlink gateway (t1120_3/t1120_6).
#
# `ait chatlink --headless` runs the Textual-free bug-intake gateway
# (chatlink/daemon.py): it watches the configured chat channel, spawns
# sandboxed agents for authorized bug reports, and relays structured Q&A.
# `ait chatlink` (no --headless) runs the read-only status TUI
# (chatlink/chatlink_app.py). The dispatch happens HERE in bash — the
# daemon module must never import Textual (guard-tested), mirroring the
# aitask_monitor.sh --headless-for-applink pattern.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

PYTHON="$(require_ait_python)"

headless=0
for arg in "$@"; do
    [[ "$arg" == "--headless" ]] && headless=1
done

if [[ $headless -eq 1 ]]; then
    # The daemon needs yaml (config loader) and the chat tier's Discord SDK
    # (live adapter) — NOT textual (headless by design).
    missing=()
    "$PYTHON" -c "import yaml"    2>/dev/null || missing+=(pyyaml)
    "$PYTHON" -c "import discord" 2>/dev/null || missing+=(discord.py)
    if [[ ${#missing[@]} -gt 0 ]]; then
        die "Missing Python packages: ${missing[*]}. Run 'ait setup' and install the chat adapter tier."
    fi

    # Sandbox tier preflight (t1120_5): warn-not-block — the daemon serves
    # without docker, but agent launches fail honestly until it is installed
    # (see aidocs/chat/chatlink_sandbox.md for the image build).
    if ! command -v docker >/dev/null 2>&1; then
        echo "chatlink: warning — 'docker' not found; sandboxed agent launches will fail until Docker is installed." >&2
    fi

    PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
        exec "$PYTHON" -m chatlink.daemon "$@"
fi

# TUI path: needs textual + yaml (paths/config resolution), never discord.
missing=()
"$PYTHON" -c "import textual" 2>/dev/null || missing+=(textual)
"$PYTHON" -c "import yaml"    2>/dev/null || missing+=(pyyaml)
if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install TUI dependencies."
fi
ait_warn_if_incapable_terminal

PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    exec "$PYTHON" -m chatlink.chatlink_app "$@"
