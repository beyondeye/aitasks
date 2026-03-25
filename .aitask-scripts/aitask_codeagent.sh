#!/usr/bin/env bash
# aitask_codeagent.sh - Unified wrapper for AI code agent invocation and model selection
# Supports Claude Code, Gemini CLI, Codex CLI, and OpenCode with configurable model selection.
#
# Agent string format: <agent>/<model>  (e.g., claudecode/opus4_6, geminicli/gemini3pro)
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
DEFAULT_AGENT_STRING="claudecode/opus4_6"
DEFAULT_COAUTHOR_DOMAIN="aitasks.io"
SUPPORTED_AGENTS=(claudecode geminicli codex opencode)
SUPPORTED_OPERATIONS=(pick explain batch-review qa raw)

# --- Global flags (set by argument parser) ---

OPT_AGENT_STRING=""
OPT_DRY_RUN=false

# --- Parsed agent string (set by parse_agent_string) ---

PARSED_AGENT=""
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
    PARSED_AGENT="${BASH_REMATCH[1]}"
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

# Resolve the project-scoped email domain used by custom code-agent coauthors.
get_coauthor_domain() {
    local config_file="$METADATA_DIR/project_config.yaml"
    local value=""

    if [[ -f "$config_file" ]]; then
        value=$(awk '
            /^[[:space:]]*codeagent_coauthor_domain:[[:space:]]*/ {
                sub(/^[^:]*:[[:space:]]*/, "", $0)
                sub(/[[:space:]]+#.*$/, "", $0)
                print
                exit
            }
        ' "$config_file")
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"
        value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    fi

    if [[ -z "$value" || "$value" == "null" ]]; then
        value="$DEFAULT_COAUTHOR_DOMAIN"
    fi

    echo "$value"
}

format_codex_model_label() {
    local raw_model="$1"

    if [[ "$raw_model" =~ ^gpt-([0-9]+)\.([0-9]+)(-(.*))?$ ]]; then
        local major="${BASH_REMATCH[1]}"
        local minor="${BASH_REMATCH[2]}"
        local suffix="${BASH_REMATCH[4]:-}"
        local label="GPT${major}.${minor}"

        if [[ -n "$suffix" ]]; then
            local segment
            IFS='-' read -r -a suffix_parts <<< "$suffix"
            for segment in "${suffix_parts[@]}"; do
                if [[ "$segment" =~ ^[0-9]+$ ]]; then
                    label+="-${segment}"
                else
                    label+="-$(tr '[:lower:]' '[:upper:]' <<< "${segment:0:1}")${segment:1}"
                fi
            done
        fi

        echo "$label"
        return
    fi

    echo "$raw_model"
}

format_claude_model_label() {
    local raw_model="$1"

    # claude-<family>-<major>-<minor>[-<date>] → <Family> <major>.<minor>
    if [[ "$raw_model" =~ ^claude-([a-z]+)-([0-9]+)-([0-9]+)(-[0-9]+)?$ ]]; then
        local family="${BASH_REMATCH[1]}"
        local major="${BASH_REMATCH[2]}"
        local minor="${BASH_REMATCH[3]}"
        # Capitalize family name
        local cap_family
        cap_family="$(tr '[:lower:]' '[:upper:]' <<< "${family:0:1}")${family:1}"
        echo "$cap_family $major.$minor"
        return
    fi

    echo "$raw_model"
}

format_gemini_model_label() {
    local raw_model="$1"

    if [[ "$raw_model" =~ ^gemini-([0-9\.]+)-([a-z]+)(-[a-z]+)?$ ]]; then
        local version="${BASH_REMATCH[1]}"
        local type="${BASH_REMATCH[2]}"
        local suffix="${BASH_REMATCH[3]:-}"
        
        local cap_type
        cap_type="$(tr '[:lower:]' '[:upper:]' <<< "${type:0:1}")${type:1}"
        
        local label="$version $cap_type"
        
        if [[ -n "$suffix" ]]; then
            suffix="${suffix:1}"
            local cap_suffix
            cap_suffix="$(tr '[:lower:]' '[:upper:]' <<< "${suffix:0:1}")${suffix:1}"
            label+=" $cap_suffix"
        fi
        
        echo "$label"
        return
    fi

    echo "$raw_model"
}

format_opencode_model_label() {
    local raw_cli_id="$1"
    # Strip provider prefix (everything before and including /)
    local model_part="${raw_cli_id##*/}"

    local result=""
    local prev_is_num=false
    local segment
    IFS='-' read -r -a segments <<< "$model_part"
    for segment in "${segments[@]}"; do
        local is_num=false
        [[ "$segment" =~ ^[0-9]+$ ]] && is_num=true

        if [[ -n "$result" ]]; then
            if $prev_is_num && $is_num; then
                # Collapse adjacent numeric segments: 4-6 → 4.6
                result+=".${segment}"
            else
                result+=" "
                case "$segment" in
                    gpt|glm) result+="$(echo "$segment" | tr '[:lower:]' '[:upper:]')" ;;
                    *) result+="$(tr '[:lower:]' '[:upper:]' <<< "${segment:0:1}")${segment:1}" ;;
                esac
            fi
        else
            case "$segment" in
                gpt|glm) result="$(echo "$segment" | tr '[:lower:]' '[:upper:]')" ;;
                *) result="$(tr '[:lower:]' '[:upper:]' <<< "${segment:0:1}")${segment:1}" ;;
            esac
        fi

        prev_is_num=$is_num
    done

    echo "$result"
}

lookup_cli_model_id_if_known() {
    local agent="$1"
    local model_name="$2"
    local models_file="$METADATA_DIR/models_${agent}.json"

    if [[ ! -f "$models_file" ]]; then
        return
    fi

    jq -r --arg name "$model_name" \
        '.models[] | select(.name == $name) | .cli_id' "$models_file" 2>/dev/null || true
}

get_agent_coauthor_name() {
    local agent="$1"
    local model_name="$2"
    local cli_id=""

    case "$agent" in
        codex)
            cli_id="$(lookup_cli_model_id_if_known "$agent" "$model_name")"
            if [[ -n "$cli_id" && "$cli_id" != "null" ]]; then
                echo "Codex/$(format_codex_model_label "$cli_id")"
            else
                echo "Codex/$model_name"
            fi
            ;;
        claudecode)
            cli_id="$(lookup_cli_model_id_if_known "$agent" "$model_name")"
            if [[ -n "$cli_id" && "$cli_id" != "null" ]]; then
                echo "Claude Code/$(format_claude_model_label "$cli_id")"
            else
                echo "Claude Code/$model_name"
            fi
            ;;
        geminicli)
            cli_id="$(lookup_cli_model_id_if_known "$agent" "$model_name")"
            if [[ -n "$cli_id" && "$cli_id" != "null" ]]; then
                echo "Gemini CLI/$(format_gemini_model_label "$cli_id")"
            else
                echo "Gemini CLI/$model_name"
            fi
            ;;
        opencode)
            cli_id="$(lookup_cli_model_id_if_known "$agent" "$model_name")"
            if [[ -n "$cli_id" && "$cli_id" != "null" ]]; then
                echo "OpenCode/$(format_opencode_model_label "$cli_id")"
            else
                echo "OpenCode/$model_name"
            fi
            ;;
        *)
            die "Coauthor metadata for agent '$agent' is not supported yet"
            ;;
    esac
}

get_agent_coauthor_email() {
    local agent="$1"
    local domain
    domain="$(get_coauthor_domain)"

    case "$agent" in
        codex) echo "codex@$domain" ;;
        claudecode) echo "claudecode@$domain" ;;
        geminicli) echo "geminicli@$domain" ;;
        opencode) echo "opencode@$domain" ;;
        *) die "Coauthor metadata for agent '$agent' is not supported yet" ;;
    esac
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
    local active_only=false
    local filter_agent=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --active-only) active_only=true; shift ;;
            -*) die "Unknown flag: '$1'" ;;
            *)  filter_agent="$1"; shift ;;
        esac
    done

    local agents_to_list=("${SUPPORTED_AGENTS[@]}")
    if [[ -n "$filter_agent" ]]; then
        local valid=false
        for a in "${SUPPORTED_AGENTS[@]}"; do
            [[ "$a" == "$filter_agent" ]] && valid=true
        done
        $valid || die "Unknown agent: '$filter_agent'. Supported: ${SUPPORTED_AGENTS[*]}"
        agents_to_list=("$filter_agent")
    fi

    local jq_filter='.models[]'
    if $active_only; then
        jq_filter='.models[] | select((.status // "active") != "unavailable")'
    fi

    for agent in "${agents_to_list[@]}"; do
        local models_file="$METADATA_DIR/models_${agent}.json"
        if [[ ! -f "$models_file" ]]; then
            warn "No model config found for '$agent' ($models_file)"
            continue
        fi

        echo "=== $agent ==="
        jq -r "$jq_filter"'
            | "MODEL:\(.name) CLI_ID:\(.cli_id) STATUS:\(.status // "active") NOTES:\(.notes) VERIFIED:\((.verified // {}) | to_entries | map("\(.key)=\(.value)") | join(","))"
              + (
                    ((.verifiedstats // {}) | to_entries | map("\(.key)(runs \(.value.runs // 0), avg \(if (.value.runs // 0) > 0 then ((.value.score_sum // 0) / (.value.runs // 0) | round) else 0 end))") | join(",")) as $stats
                    | if $stats == "" then "" else "\nSTATS:\($stats)" end
                )
        ' "$models_file"
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

cmd_coauthor_domain() {
    echo "COAUTHOR_DOMAIN:$(get_coauthor_domain)"
}

cmd_coauthor() {
    local agent_string="${1:-}"
    [[ -z "$agent_string" ]] && die "Usage: ait codeagent coauthor <agent-string>"

    parse_agent_string "$agent_string"

    local coauthor_name
    coauthor_name="$(get_agent_coauthor_name "$PARSED_AGENT" "$PARSED_MODEL")"
    local coauthor_email
    coauthor_email="$(get_agent_coauthor_email "$PARSED_AGENT")"

    echo "AGENT_STRING:$agent_string"
    echo "AGENT_COAUTHOR_NAME:$coauthor_name"
    echo "AGENT_COAUTHOR_EMAIL:$coauthor_email"
    echo "AGENT_COAUTHOR_TRAILER:Co-Authored-By: $coauthor_name <$coauthor_email>"
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
        claudecode)
            case "$operation" in
                pick)
                    # claude --model <id> "/aitask-pick <args>"
                    CMD+=("/aitask-pick ${args[*]}")
                    ;;
                explain)
                    # claude --model <id> "/aitask-explain <args>"
                    CMD+=("/aitask-explain ${args[*]}")
                    ;;
                qa)
                    # claude --model <id> "/aitask-qa <args>"
                    CMD+=("/aitask-qa ${args[*]}")
                    ;;
                batch-review)
                    CMD+=("--print" "${args[@]}")
                    ;;
                raw)
                    CMD+=("${args[@]}")
                    ;;
            esac
            ;;
        geminicli)
            case "$operation" in
                pick)
                    CMD+=("/aitask-pick ${args[*]}")
                    ;;
                explain)
                    CMD+=("/aitask-explain ${args[*]}")
                    ;;
                qa)
                    CMD+=("/aitask-qa ${args[*]}")
                    ;;
                batch-review|raw)
                    CMD+=("${args[@]}")
                    ;;
            esac
            ;;
        codex)
            case "$operation" in
                pick)
                    CMD+=("\$aitask-pick ${args[*]}")
                    ;;
                explain)
                    CMD+=("\$aitask-explain ${args[*]}")
                    ;;
                qa)
                    CMD+=("\$aitask-qa ${args[*]}")
                    ;;
                batch-review|raw)
                    CMD+=("${args[@]}")
                    ;;
            esac
            ;;
        opencode)
            case "$operation" in
                pick)
                    CMD+=("--prompt" "/aitask-pick ${args[*]}")
                    ;;
                explain)
                    CMD+=("--prompt" "/aitask-explain ${args[*]}")
                    ;;
                qa)
                    CMD+=("--prompt" "/aitask-qa ${args[*]}")
                    ;;
                batch-review|raw)
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

    # Export agent string for skill tracking (implemented_with metadata)
    local agent_string
    agent_string=$(resolve_agent_string "$operation")
    export AITASK_AGENT_STRING="$agent_string"

    exec "${CMD[@]}"
}

# --- Help ---

show_help() {
    cat << 'EOF'
Usage: ait codeagent <command> [options]

Commands:
  list-agents            List supported code agents and CLI availability
  list-models [--active-only] [AGENT]
                         List models for an agent (with verification scores and status)
  resolve <operation>    Return configured agent string for an operation
  coauthor <agent-string>
                         Return commit coauthor metadata for an agent string
  coauthor-domain        Return the configured code-agent coauthor email domain
  check <agent-string>   Validate agent string and check CLI availability
  invoke <operation> [args...]  Invoke the code agent for an operation

Options:
  --agent-string STR     Override agent string (e.g., claudecode/opus4_6)
  --dry-run              Print command without executing (for invoke)
  -h, --help             Show this help

Operations: pick, explain, batch-review, qa, raw
Agent string format: <agent>/<model> (e.g., claudecode/opus4_6, geminicli/gemini3pro)

Resolution chain (highest priority first):
  1. --agent-string flag
  2. aitasks/metadata/codeagent_config.local.json (per-user, gitignored)
  3. aitasks/metadata/codeagent_config.json (per-project, git-tracked)
  4. Hardcoded default: claudecode/opus4_6

Examples:
  ait codeagent list-agents
  ait codeagent list-models claudecode
  ait codeagent resolve pick
  ait codeagent coauthor codex/gpt5_4
  ait codeagent coauthor-domain
  ait codeagent check "claudecode/opus4_6"
  ait codeagent invoke pick 42
  ait codeagent --agent-string geminicli/gemini2_5pro invoke explain src/
  ait codeagent --dry-run invoke pick 42
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
        coauthor)     cmd_coauthor "$@" ;;
        coauthor-domain) cmd_coauthor_domain "$@" ;;
        check)        cmd_check "$@" ;;
        invoke)       cmd_invoke "$@" ;;
        *)            die "Unknown command: '$command'. Run 'ait codeagent --help' for usage." ;;
    esac
}

main "$@"
