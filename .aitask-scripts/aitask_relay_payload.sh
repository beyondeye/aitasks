#!/usr/bin/env bash
# aitask_relay_payload.sh — agent-side task-payload writer for the chatlink
# Q&A relay.
#
# Thin wrapper over `chatlink/relay_payload.py` (the Python core owns
# argparse, schema validation via the shared TaskPayload dataclass, and the
# atomic spool write). Runs inside the spawned — possibly sandboxed — agent,
# so it depends only on python3 + stdlib and never imports chat/ or
# framework modules.
#
# Usage:
#   aitask_relay_payload.sh --relay-dir <session_dir> \
#       --name <slug> --title "<title>" --priority high|medium|low \
#       --effort high|medium|low --issue-type <type> \
#       [--labels a,b,c] --description-file <path|->
#
# Output (stdout): PAYLOAD_WRITTEN:<path> on success. Exit 0 on success;
# exit 2 on usage/validation errors (ERROR:<reason> on stderr, nothing
# written).
#
# Spec: aidocs/chat/qa_relay_protocol.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v python3 >/dev/null 2>&1 || {
    echo "ERROR:python3 not found" >&2
    exit 2
}

PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    exec python3 -m chatlink.relay_payload "$@"
