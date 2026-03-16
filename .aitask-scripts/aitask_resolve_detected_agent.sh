#!/usr/bin/env bash
# aitask_resolve_detected_agent.sh - Resolve detected agent/model into agent string
# Encapsulates the JSON lookup so code agents don't need to parse models JSON manually.
#
# Usage: ./.aitask-scripts/aitask_resolve_detected_agent.sh --agent <agent> --cli-id <model_id>
#
# Output (single line, always exit 0):
#   AGENT_STRING:<agent>/<name>            — exact match found
#   AGENT_STRING:<agent>/<name>            — suffix match found (opencode only)
#   AGENT_STRING_FALLBACK:<agent>/<cli_id> — no match, raw cli_id used
#
# If AITASK_AGENT_STRING env var is set, outputs it directly (fast path).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

METADATA_DIR="${TASK_DIR:-aitasks}/metadata"
SUPPORTED_AGENTS=(claudecode geminicli codex opencode)

# --- Fast path: env var override ---
if [[ -n "${AITASK_AGENT_STRING:-}" ]]; then
    echo "AGENT_STRING:${AITASK_AGENT_STRING}"
    exit 0
fi

# --- Argument parsing ---
agent=""
cli_id=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --agent)
            agent="$2"
            shift 2
            ;;
        --cli-id)
            cli_id="$2"
            shift 2
            ;;
        *)
            die "Unknown argument: $1. Usage: aitask_resolve_detected_agent.sh --agent <agent> --cli-id <model_id>"
            ;;
    esac
done

if [[ -z "$agent" ]]; then
    die "Missing required argument: --agent"
fi
if [[ -z "$cli_id" ]]; then
    die "Missing required argument: --cli-id"
fi

# --- Validate agent ---
valid=false
for a in "${SUPPORTED_AGENTS[@]}"; do
    if [[ "$a" == "$agent" ]]; then
        valid=true
        break
    fi
done
if [[ "$valid" != "true" ]]; then
    die "Invalid agent: $agent. Must be one of: ${SUPPORTED_AGENTS[*]}"
fi

# --- Locate models file ---
models_file="$METADATA_DIR/models_${agent}.json"
if [[ ! -f "$models_file" ]]; then
    echo "AGENT_STRING_FALLBACK:${agent}/${cli_id}"
    exit 0
fi

# --- Exact match ---
name=$(jq -r --arg id "$cli_id" '.models[] | select(.cli_id == $id) | .name' "$models_file" | head -1)
if [[ -n "$name" ]]; then
    echo "AGENT_STRING:${agent}/${name}"
    exit 0
fi

# --- Suffix match (opencode only) ---
if [[ "$agent" == "opencode" ]]; then
    name=$(jq -r --arg id "$cli_id" '.models[] | select(.cli_id | endswith("/" + $id)) | .name' "$models_file" | head -1)
    if [[ -n "$name" ]]; then
        echo "AGENT_STRING:${agent}/${name}"
        exit 0
    fi
fi

# --- Fallback ---
echo "AGENT_STRING_FALLBACK:${agent}/${cli_id}"
exit 0
