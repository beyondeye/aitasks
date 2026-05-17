#!/usr/bin/env bash
# agent_string.sh - Single source of truth for agent-string parsing and
# model/binary/flag resolution. Sourceable from any aitask script that
# needs to translate "<agent>/<model>" into the per-CLI invocation triple
# (binary, model_flag, cli_id).
#
# Provides:
#   SUPPORTED_AGENTS           (array of canonical agent names)
#   DEFAULT_AGENT_STRING       (claudecode/opus4_7_1m at time of writing)
#   METADATA_DIR               (defaults to ${TASK_DIR:-aitasks}/metadata)
#   PARSED_AGENT / PARSED_MODEL (set by parse_agent_string)
#   parse_agent_string <s>     (sets PARSED_AGENT, PARSED_MODEL; dies on bad input)
#   get_cli_binary <agent>     (e.g. claudecode -> claude)
#   get_model_flag <agent>     (e.g. claudecode -> --model)
#   get_cli_model_id <agent> <model>  (reads models_<agent>.json via jq)
#   require_jq                 (dies if jq is missing)

[[ -n "${_AIT_AGENT_STRING_LOADED:-}" ]] && return 0
_AIT_AGENT_STRING_LOADED=1

# shellcheck source=terminal_compat.sh
source "$(dirname "${BASH_SOURCE[0]}")/terminal_compat.sh"

# --- Constants (caller may pre-set any of these to override) ---

DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus4_7_1m}"
METADATA_DIR="${METADATA_DIR:-${TASK_DIR:-aitasks}/metadata}"
SUPPORTED_AGENTS=(claudecode geminicli codex opencode)

# --- Parsed agent string (set by parse_agent_string; read by callers in
# aitask_codeagent.sh and aitask_skillrun.sh after sourcing) ---

# shellcheck disable=SC2034
PARSED_AGENT=""
# shellcheck disable=SC2034
PARSED_MODEL=""

# --- Utility functions ---

require_jq() {
    if ! command -v jq &>/dev/null; then
        die "jq is required. Install via your package manager."
    fi
}

# Validate and parse an agent string like "claudecode/opus4_6"
# Sets PARSED_AGENT and PARSED_MODEL
parse_agent_string() {
    local agent_string="$1"
    if [[ ! "$agent_string" =~ ^([a-z]+)/([a-z0-9_]+)$ ]]; then
        die "Invalid agent string format: '$agent_string'. Expected: <agent>/<model> (e.g., claudecode/opus4_6)"
    fi
    # shellcheck disable=SC2034  # Read by callers after sourcing this lib.
    PARSED_AGENT="${BASH_REMATCH[1]}"
    # shellcheck disable=SC2034  # Read by callers after sourcing this lib.
    PARSED_MODEL="${BASH_REMATCH[2]}"

    # Validate agent is supported
    local valid=false
    for a in "${SUPPORTED_AGENTS[@]}"; do
        [[ "$a" == "$PARSED_AGENT" ]] && valid=true
    done
    if ! $valid; then
        die "Unknown agent: '$PARSED_AGENT'. Supported: ${SUPPORTED_AGENTS[*]}"
    fi
}

# Map agent name to CLI binary name
get_cli_binary() {
    local agent="$1"
    case "$agent" in
        claudecode) echo "claude" ;;
        geminicli)  echo "gemini" ;;
        codex)    echo "codex" ;;
        opencode) echo "opencode" ;;
        *) die "Unknown agent: '$agent'" ;;
    esac
}

# Map agent name to the CLI flag used for model selection
get_model_flag() {
    local agent="$1"
    case "$agent" in
        claudecode) echo "--model" ;;
        geminicli)  echo "-m" ;;
        codex)    echo "-m" ;;
        opencode) echo "--model" ;;
        *) die "Unknown agent: '$agent'" ;;
    esac
}

# Look up the CLI model ID from the model config JSON
# Usage: get_cli_model_id <agent> <model_name>
get_cli_model_id() {
    local agent="$1"
    local model_name="$2"
    local models_file="$METADATA_DIR/models_${agent}.json"

    if [[ ! -f "$models_file" ]]; then
        die "Model config not found: $models_file"
    fi

    local cli_id
    cli_id=$(jq -r --arg name "$model_name" \
        '.models[] | select(.name == $name) | .cli_id' "$models_file")

    if [[ -z "$cli_id" || "$cli_id" == "null" ]]; then
        die "Unknown model '$model_name' for agent '$agent'. Run 'ait codeagent list-models $agent' to see available models."
    fi

    # Check model status (defaults to "active" for files without status field)
    local model_status
    model_status=$(jq -r --arg name "$model_name" \
        '.models[] | select(.name == $name) | .status // "active"' "$models_file")

    if [[ "$model_status" == "unavailable" ]]; then
        die "Model '$model_name' is unavailable (not currently marked as available by connected providers). Run 'ait opencode-models' to refresh."
    fi

    echo "$cli_id"
}
