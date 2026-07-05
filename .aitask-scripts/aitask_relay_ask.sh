#!/usr/bin/env bash
# aitask_relay_ask.sh — agent-side blocking ask for the chatlink Q&A relay.
#
# Thin wrapper over `chatlink/relay_ask.py` (the Python core owns argparse,
# spool I/O, and the durable-timeout rule). Runs inside the spawned —
# possibly sandboxed — agent, so it depends only on python3 + stdlib and
# never imports chat/ or framework modules.
#
# Usage:
#   aitask_relay_ask.sh --relay-dir <session_dir> --text "Which module?" \
#       [--header "Module"] [--option "label::desc"]... \
#       [--multi-select] [--free-text] [--timeout 90]
#
# Output (stdout): STATUS:answered|timeout|cancelled, then VALUE:<label>
# lines and/or FREE_TEXT:<text>. Exit 0 on any terminal answer status
# (timeout is fail-safe, not an error); exit 2 on usage/environment errors.
#
# Spec: aidocs/chat/qa_relay_protocol.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v python3 >/dev/null 2>&1 || {
    echo "ERROR:python3 not found" >&2
    exit 2
}

PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    exec python3 -m chatlink.relay_ask "$@"
