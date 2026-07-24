#!/usr/bin/env bash
# aitask_codeagent.sh - Unified wrapper for AI code agent invocation and model selection
# Supports Claude Code, Codex CLI, and OpenCode with configurable model selection.
#
# Agent string format: <agent>/<model>  (e.g., claudecode/opus4_6, codex/gpt5_4)
#
# Usage: ait codeagent <command> [options]
# Run 'ait codeagent --help' for details.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh disable=SC1091
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/agent_string.sh disable=SC1091
source "$SCRIPT_DIR/lib/agent_string.sh"

# --- Constants ---
# DEFAULT_AGENT_STRING, METADATA_DIR, SUPPORTED_AGENTS, PARSED_AGENT, PARSED_MODEL,
# parse_agent_string, get_cli_binary, get_model_flag, get_cli_model_id, require_jq
# come from lib/agent_string.sh.

DEFAULT_COAUTHOR_DOMAIN="aitasks.io"
SUPPORTED_OPERATIONS=(pick explain batch-review qa explore explore-relay raw shadow learn work-report trail)

# --- Global flags (set by argument parser) ---

OPT_AGENT_STRING=""
OPT_DRY_RUN=false
# Opt-in headless mode. Affects `claudecode batch-review` (appends `--print`;
# default interactive) and is REQUIRED for `explore-relay` (headless-only —
# refuses without it); a no-op for every other agent/operation. Opt-in,
# because Claude Code bills headless print mode at a higher per-token rate.
OPT_HEADLESS=false

# --- explore-relay constants (chat-native explore; t1120_4) ---
# Env contract pinned in aiplans/p1120/p1120_4_chat_native_explore.md:
# CHATLINK_RELAY_DIR (per-session spool dir) + CHATLINK_BUG_REPORT_FILE.
# Tool-timeout budget is engine-owned: the spawned agent's Bash tool must
# outlive the relay helper's 540 s question deadline, so both Claude Code
# timeout controls are exported at dispatch (630 s > 540 s helper deadline;
# the skill also passes the per-call timeout parameter — belt and braces).
EXPLORE_RELAY_TOOL_TIMEOUT_MS=630000
EXPLORE_RELAY_ALLOWED_TOOLS="Bash,Read,Write,Glob,Grep"

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
build_skill_prompt() {
    local skill="$1"
    shift || true
    if [[ $# -gt 0 ]]; then
        printf '%s %s' "$skill" "$*"
    else
        printf '%s' "$skill"
    fi
}

build_invoke_command() {
    local operation="$1"
    shift
    local args=("$@")

    local agent_string
    agent_string=$(resolve_agent_string "$operation")
    parse_agent_string "$agent_string"

    # Operation-support gate BEFORE model resolution: an unsupported
    # agent/operation pair must refuse with its own reason, not a
    # misleading model-availability error.
    if [[ "$operation" == "explore-relay" && "$PARSED_AGENT" != "claudecode" ]]; then
        die "explore-relay is not yet supported for $PARSED_AGENT (Claude Code only; port tracked as a follow-up task)"
    fi

    # work-report and trail pass identity fields (column IDs, task IDs,
    # artifact handles, topic csv) through a whitespace-joined slash-command
    # string; an arg containing whitespace would split undetectably, so
    # refuse it outright. Checked before per-agent dispatch and under
    # --dry-run so refusals are unit-testable.
    if [[ "$operation" == "work-report" || "$operation" == "trail" ]]; then
        local wr_arg
        for wr_arg in "${args[@]}"; do
            if [[ "$wr_arg" =~ [[:space:]] ]]; then
                die "$operation argument contains whitespace — slash-command text cannot preserve argument boundaries: '$wr_arg'"
            fi
        done
    fi

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
                explore)
                    CMD+=("/aitask-explore")
                    ;;
                shadow)
                    # claude --model <id> "/aitask-shadow <pane_id> [<task_id>]"
                    CMD+=("/aitask-shadow ${args[*]}")
                    ;;
                learn)
                    # claude --model <id> "/aitask-learn-skill <pane_id|source>"
                    CMD+=("/aitask-learn-skill ${args[*]}")
                    ;;
                work-report)
                    # claude --model <id> "/aitask-work-report <args>"
                    CMD+=("/aitask-work-report ${args[*]}")
                    ;;
                trail)
                    # claude --model <id> "/aitask-trail <args>"
                    CMD+=("/aitask-trail ${args[*]}")
                    ;;
                batch-review)
                    # Interactive by default (no billing surcharge); opt into
                    # headless `--print` only when --headless was passed.
                    if [[ "$OPT_HEADLESS" == true ]]; then
                        CMD+=("--print" "${args[@]}")
                    else
                        CMD+=("${args[@]}")
                    fi
                    ;;
                explore-relay)
                    # Chat-native explore (t1120_4): headless-only, machine-
                    # spawned by the chatlink gateway. Unlike batch-review
                    # there is no interactive fallback — a relay-driven flow
                    # has no terminal user — so refuse without --headless
                    # (explicit opt-in to Claude Code's headless billing
                    # surcharge).
                    if [[ "$OPT_HEADLESS" != true ]]; then
                        die "explore-relay is headless-only; pass --headless to accept Claude Code's headless billing surcharge"
                    fi
                    # Env preconditions (distinct reasons; checked even under
                    # --dry-run so refusals are unit-testable).
                    if [[ -z "${CHATLINK_RELAY_DIR:-}" || ! -d "${CHATLINK_RELAY_DIR:-}" ]]; then
                        die "explore-relay requires CHATLINK_RELAY_DIR to point at an existing relay session directory"
                    fi
                    if [[ -z "${CHATLINK_BUG_REPORT_FILE:-}" || ! -f "${CHATLINK_BUG_REPORT_FILE:-}" ]]; then
                        die "explore-relay requires CHATLINK_BUG_REPORT_FILE to point at an existing bug-report file"
                    fi
                    # Rebuild CMD with an `env` prefix so the tool-timeout
                    # exports are engine-owned AND visible in --dry-run.
                    # Natural slash-command in print mode (never inline the
                    # rendered SKILL.md via -p); --allowedTools is required
                    # headless (no permission prompts are possible). The
                    # prompt MUST precede --allowedTools: the flag is
                    # variadic and would swallow a trailing positional.
                    CMD=(env
                        "BASH_DEFAULT_TIMEOUT_MS=$EXPLORE_RELAY_TOOL_TIMEOUT_MS"
                        "BASH_MAX_TIMEOUT_MS=$EXPLORE_RELAY_TOOL_TIMEOUT_MS"
                        "$binary" "$model_flag" "$cli_id"
                        "--print" "/aitask-explorechat"
                        "--allowedTools" "$EXPLORE_RELAY_ALLOWED_TOOLS")
                    ;;
                raw)
                    CMD+=("${args[@]}")
                    ;;
            esac
            ;;
        codex)
            case "$operation" in
                batch-review|raw)
                    CMD+=("${args[@]}")
                    ;;
                *)
                    # Skill launches: build the $aitask-* composer prompt and
                    # launch Codex directly in its default mode. Interactive
                    # prompts work there via the default_mode_request_user_input
                    # feature flag that `ait setup` enables.
                    local prompt
                    case "$operation" in
                        pick)    prompt=$(build_skill_prompt "\$aitask-pick" "${args[@]}") ;;
                        explain) prompt=$(build_skill_prompt "\$aitask-explain" "${args[@]}") ;;
                        qa)      prompt=$(build_skill_prompt "\$aitask-qa" "${args[@]}") ;;
                        explore) prompt=$(build_skill_prompt "\$aitask-explore") ;;
                        shadow)  prompt=$(build_skill_prompt "\$aitask-shadow" "${args[@]}") ;;
                        learn)   prompt=$(build_skill_prompt "\$aitask-learn-skill" "${args[@]}") ;;
                        work-report) prompt=$(build_skill_prompt "\$aitask-work-report" "${args[@]}") ;;
                        trail)   prompt=$(build_skill_prompt "\$aitask-trail" "${args[@]}") ;;
                    esac
                    CMD=("$binary" "$model_flag" "$cli_id" "$prompt")
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
                explore)
                    CMD+=("--prompt" "/aitask-explore")
                    ;;
                shadow)
                    CMD+=("--prompt" "/aitask-shadow ${args[*]}")
                    ;;
                learn)
                    CMD+=("--prompt" "/aitask-learn-skill ${args[*]}")
                    ;;
                work-report)
                    CMD+=("--prompt" "/aitask-work-report ${args[*]}")
                    ;;
                trail)
                    CMD+=("--prompt" "/aitask-trail ${args[*]}")
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
        printf 'DRY_RUN:'
        printf ' %q' "${CMD[@]}"
        printf '\n'
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
  --headless             Run claudecode batch-review non-interactively (adds
                         --print); REQUIRED for explore-relay, which is
                         headless-only and refuses without it. No-op for
                         other agents/operations. Default is interactive
                         (avoids Claude Code's headless billing surcharge).
  -h, --help             Show this help

Operations: pick, explain, batch-review, qa, explore, explore-relay, raw,
            shadow, learn, work-report, trail
  explore-relay: chat-native explore spawned by the chatlink gateway
  (claudecode only). Requires --headless plus CHATLINK_RELAY_DIR and
  CHATLINK_BUG_REPORT_FILE in the environment.
Agent string format: <agent>/<model> (e.g., claudecode/opus4_6, codex/gpt5_4)

Resolution chain (highest priority first):
  1. --agent-string flag
  2. aitasks/metadata/codeagent_config.local.json (per-user, gitignored)
  3. aitasks/metadata/codeagent_config.json (per-project, git-tracked)
  4. Hardcoded default: claudecode/opus4_8

Examples:
  ait codeagent list-agents
  ait codeagent list-models claudecode
  ait codeagent resolve pick
  ait codeagent coauthor codex/gpt5_4
  ait codeagent coauthor-domain
  ait codeagent check "claudecode/opus4_6"
  ait codeagent invoke pick 42
  ait codeagent --agent-string codex/gpt5_4 invoke explain src/
  ait codeagent --dry-run invoke pick 42
  ait codeagent --headless invoke batch-review src/
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
            --headless)
                OPT_HEADLESS=true
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
