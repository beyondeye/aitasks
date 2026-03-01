#!/usr/bin/env bash
# aitask_codeagent.sh - Unified wrapper for AI code agent invocation and model selection
# Supports Claude Code, Gemini CLI, Codex CLI, and OpenCode with configurable model selection.
#
# Agent string format: <agent>/<model>  (e.g., claude/opus4_6, gemini/gemini3pro)
#
# Usage: ait codeagent <command> [options]
# Run 'ait codeagent --help' for details.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Constants ---

METADATA_DIR="${TASK_DIR:-aitasks}/metadata"
DEFAULT_AGENT_STRING="claude/opus4_6"
SUPPORTED_AGENTS=(claude gemini codex opencode)
SUPPORTED_OPERATIONS=(task-pick explain batch-review raw)

# --- Global flags (set by argument parser) ---

OPT_AGENT_STRING=""
OPT_DRY_RUN=false

# --- Parsed agent string (set by parse_agent_string) ---

PARSED_AGENT=""
PARSED_MODEL=""

# --- Utility functions ---

require_jq() {
    command -v jq &>/dev/null || die "jq is required. Install via your package manager."
}

# Validate and parse an agent string like "claude/opus4_6"
# Sets PARSED_AGENT and PARSED_MODEL
parse_agent_string() {
    local agent_string="$1"
    if [[ ! "$agent_string" =~ ^([a-z]+)/([a-z0-9_]+)$ ]]; then
        die "Invalid agent string format: '$agent_string'. Expected: <agent>/<model> (e.g., claude/opus4_6)"
    fi
    PARSED_AGENT="${BASH_REMATCH[1]}"
    PARSED_MODEL="${BASH_REMATCH[2]}"

    # Validate agent is supported
    local valid=false
    for a in "${SUPPORTED_AGENTS[@]}"; do
        [[ "$a" == "$PARSED_AGENT" ]] && valid=true
    done
    $valid || die "Unknown agent: '$PARSED_AGENT'. Supported: ${SUPPORTED_AGENTS[*]}"
}

# Map agent name to CLI binary name
get_cli_binary() {
    local agent="$1"
    case "$agent" in
        claude)   echo "claude" ;;
        gemini)   echo "gemini" ;;
        codex)    echo "codex" ;;
        opencode) echo "opencode" ;;
        *) die "Unknown agent: '$agent'" ;;
    esac
}

# Map agent name to the CLI flag used for model selection
get_model_flag() {
    local agent="$1"
    case "$agent" in
        claude)   echo "--model" ;;
        gemini)   echo "-m" ;;
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

    echo "$cli_id"
}

# Resolve the agent string for an operation using the resolution chain:
# 1. --agent-string flag
# 2. Per-user config (codeagent_config.local.json, gitignored)
# 3. Per-project config (codeagent_config.json, git-tracked)
# 4. Hardcoded default
resolve_agent_string() {
    local operation="$1"

    # 1. Explicit override
    if [[ -n "${OPT_AGENT_STRING:-}" ]]; then
        echo "$OPT_AGENT_STRING"
        return
    fi

    # 2. Per-user config (gitignored)
    local user_config="$METADATA_DIR/codeagent_config.local.json"
    if [[ -f "$user_config" ]]; then
        local user_val
        user_val=$(jq -r --arg op "$operation" '.defaults[$op] // empty' "$user_config" 2>/dev/null) || true
        if [[ -n "$user_val" ]]; then
            echo "$user_val"
            return
        fi
    fi

    # 3. Per-project config
    local project_config="$METADATA_DIR/codeagent_config.json"
    if [[ -f "$project_config" ]]; then
        local proj_val
        proj_val=$(jq -r --arg op "$operation" '.defaults[$op] // empty' "$project_config" 2>/dev/null) || true
        if [[ -n "$proj_val" ]]; then
            echo "$proj_val"
            return
        fi
    fi

    # 4. Hardcoded default
    echo "$DEFAULT_AGENT_STRING"
}

# --- Subcommands ---

cmd_list_agents() {
    for agent in "${SUPPORTED_AGENTS[@]}"; do
        local binary
        binary=$(get_cli_binary "$agent")
        local status="not-found"
        if command -v "$binary" &>/dev/null; then
            status="available"
        fi
        echo "AGENT:$agent BINARY:$binary STATUS:$status"
    done
}

cmd_list_models() {
    local filter_agent="${1:-}"

    local agents_to_list=("${SUPPORTED_AGENTS[@]}")
    if [[ -n "$filter_agent" ]]; then
        local valid=false
        for a in "${SUPPORTED_AGENTS[@]}"; do
            [[ "$a" == "$filter_agent" ]] && valid=true
        done
        $valid || die "Unknown agent: '$filter_agent'. Supported: ${SUPPORTED_AGENTS[*]}"
        agents_to_list=("$filter_agent")
    fi

    for agent in "${agents_to_list[@]}"; do
        local models_file="$METADATA_DIR/models_${agent}.json"
        if [[ ! -f "$models_file" ]]; then
            warn "No model config found for '$agent' ($models_file)"
            continue
        fi

        echo "=== $agent ==="
        jq -r '.models[] | "MODEL:\(.name) CLI_ID:\(.cli_id) NOTES:\(.notes) VERIFIED:\(.verified | to_entries | map("\(.key)=\(.value)") | join(","))"' "$models_file"
        echo ""
    done
}

cmd_resolve() {
    local operation="${1:-}"
    [[ -z "$operation" ]] && die "Usage: ait codeagent resolve <operation>"

    # Validate operation
    local valid=false
    for op in "${SUPPORTED_OPERATIONS[@]}"; do
        [[ "$op" == "$operation" ]] && valid=true
    done
    $valid || die "Unknown operation: '$operation'. Supported: ${SUPPORTED_OPERATIONS[*]}"

    local agent_string
    agent_string=$(resolve_agent_string "$operation")
    echo "AGENT_STRING:$agent_string"

    # Also output resolved components
    parse_agent_string "$agent_string"
    local cli_id
    cli_id=$(get_cli_model_id "$PARSED_AGENT" "$PARSED_MODEL")
    local model_flag
    model_flag=$(get_model_flag "$PARSED_AGENT")
    echo "AGENT:$PARSED_AGENT"
    echo "MODEL:$PARSED_MODEL"
    echo "CLI_ID:$cli_id"
    echo "BINARY:$(get_cli_binary "$PARSED_AGENT")"
    echo "MODEL_FLAG:$model_flag"
}

cmd_check() {
    local agent_string="${1:-}"
    [[ -z "$agent_string" ]] && die "Usage: ait codeagent check <agent-string>"

    parse_agent_string "$agent_string"

    # Check model exists in config
    local cli_id
    cli_id=$(get_cli_model_id "$PARSED_AGENT" "$PARSED_MODEL")

    # Check CLI binary available
    local binary
    binary=$(get_cli_binary "$PARSED_AGENT")
    local model_flag
    model_flag=$(get_model_flag "$PARSED_AGENT")

    if command -v "$binary" &>/dev/null; then
        success "OK: $agent_string -> $binary $model_flag $cli_id (binary found)"
    else
        die "Agent '$PARSED_AGENT' CLI binary '$binary' not found in PATH"
    fi
}

# Build the command array for invoking an agent
# Sets the CMD array variable
build_invoke_command() {
    local operation="$1"
    shift
    local args=("$@")

    local agent_string
    agent_string=$(resolve_agent_string "$operation")
    parse_agent_string "$agent_string"

    local binary cli_id model_flag
    binary=$(get_cli_binary "$PARSED_AGENT")
    cli_id=$(get_cli_model_id "$PARSED_AGENT" "$PARSED_MODEL")
    model_flag=$(get_model_flag "$PARSED_AGENT")

    CMD=("$binary" "$model_flag" "$cli_id")

    case "$PARSED_AGENT" in
        claude)
            case "$operation" in
                task-pick)
                    # claude --model <id> "/aitask-pick <args>"
                    CMD+=("/aitask-pick ${args[*]}")
                    ;;
                explain)
                    # claude --model <id> "/aitask-explain <args>"
                    CMD+=("/aitask-explain ${args[*]}")
                    ;;
                batch-review)
                    CMD+=("--print" "${args[@]}")
                    ;;
                raw)
                    CMD+=("${args[@]}")
                    ;;
            esac
            ;;
        gemini)
            case "$operation" in
                task-pick)
                    CMD+=("/aitask-pick ${args[*]}")
                    ;;
                explain)
                    CMD+=("/aitask-explain ${args[*]}")
                    ;;
                batch-review|raw)
                    CMD+=("${args[@]}")
                    ;;
            esac
            ;;
        codex)
            case "$operation" in
                task-pick|explain|batch-review|raw)
                    CMD+=("${args[@]}")
                    ;;
            esac
            ;;
        opencode)
            case "$operation" in
                task-pick|explain|batch-review|raw)
                    CMD+=("${args[@]}")
                    ;;
            esac
            ;;
    esac
}

cmd_invoke() {
    local operation="${1:-}"
    [[ -z "$operation" ]] && die "Usage: ait codeagent invoke <operation> [args...]"
    shift

    # Validate operation
    local valid=false
    for op in "${SUPPORTED_OPERATIONS[@]}"; do
        [[ "$op" == "$operation" ]] && valid=true
    done
    $valid || die "Unknown operation: '$operation'. Supported: ${SUPPORTED_OPERATIONS[*]}"

    local CMD=()
    build_invoke_command "$operation" "$@"

    if [[ "$OPT_DRY_RUN" == true ]]; then
        echo "DRY_RUN: ${CMD[*]}"
        return
    fi

    exec "${CMD[@]}"
}

# --- Help ---

show_help() {
    cat << 'EOF'
Usage: ait codeagent <command> [options]

Commands:
  list-agents            List supported code agents and CLI availability
  list-models [AGENT]    List models for an agent (with verification scores)
  resolve <operation>    Return configured agent string for an operation
  check <agent-string>   Validate agent string and check CLI availability
  invoke <operation> [args...]  Invoke the code agent for an operation

Options:
  --agent-string STR     Override agent string (e.g., claude/opus4_6)
  --dry-run              Print command without executing (for invoke)
  -h, --help             Show this help

Operations: task-pick, explain, batch-review, raw
Agent string format: <agent>/<model> (e.g., claude/opus4_6, gemini/gemini3pro)

Resolution chain (highest priority first):
  1. --agent-string flag
  2. aitasks/metadata/codeagent_config.local.json (per-user, gitignored)
  3. aitasks/metadata/codeagent_config.json (per-project, git-tracked)
  4. Hardcoded default: claude/opus4_6

Examples:
  ait codeagent list-agents
  ait codeagent list-models claude
  ait codeagent resolve task-pick
  ait codeagent check "claude/opus4_6"
  ait codeagent invoke task-pick 42
  ait codeagent --agent-string gemini/gemini2_5pro invoke explain src/
  ait codeagent --dry-run invoke task-pick 42
EOF
}

# --- Main ---

main() {
    require_jq

    # Parse global flags first, collecting positional args
    local positional=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent-string)
                [[ $# -lt 2 ]] && die "--agent-string requires a value"
                OPT_AGENT_STRING="$2"
                shift 2
                ;;
            --dry-run)
                OPT_DRY_RUN=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                positional+=("$1")
                shift
                ;;
        esac
    done

    set -- "${positional[@]+"${positional[@]}"}"

    local command="${1:-}"
    [[ -z "$command" ]] && { show_help; exit 0; }
    shift

    case "$command" in
        list-agents)  cmd_list_agents "$@" ;;
        list-models)  cmd_list_models "$@" ;;
        resolve)      cmd_resolve "$@" ;;
        check)        cmd_check "$@" ;;
        invoke)       cmd_invoke "$@" ;;
        *)            die "Unknown command: '$command'. Run 'ait codeagent --help' for usage." ;;
    esac
}

main "$@"
