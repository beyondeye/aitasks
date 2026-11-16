#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/verified_update_lib.sh"

# Anchor to the repo root before anything resolves a relative path: the registry
# check reads `aitasks/metadata/models_<agent>.json` relative to the cwd, and the
# stats CLI is pointed at the cwd as the project root. From a subdirectory the
# former would die with "Model config not found" (t1658_2).
ait_cd_repo_root "$SCRIPT_DIR"

SUPPORTED_AGENTS=(claudecode codex opencode)

AGENT_STRING=""
CLI_AGENT=""
CLI_ID=""
SKILL_NAME=""
SCORE=""
SILENT=false
DATE_OVERRIDE=""

PARSED_AGENT=""
PARSED_MODEL=""

show_help() {
    cat <<'EOF'
Usage: aitask_verified_update.sh [--agent-string <agent/model> | --agent <name> --cli-id <id>] --skill <skill> --score <1-5> [--date YYYY-MM-DD] [--silent]

Update rolling verification statistics for a model/skill pair.

Storage:
  The counters (verifiedstats) live on the `aitask-stats` plumbing branch
  (written by aitask_model_stats.py), never in models_<agent>.json. A run does
  not fetch, merge, rebase or push the task-data branch and does not touch its
  worktree or index. The registry file is only read, to check that the model
  exists. Its `verified` score is a static prior and is never written: readers
  derive the effective score from verifiedstats.

Options:
  --agent-string STR  Agent string in the form <agent>/<model>
  --agent NAME        Agent name (claudecode, codex, opencode)
  --cli-id ID         Raw model ID from agent runtime (e.g. claude-opus-4-6)
                      Use --agent + --cli-id as alternative to --agent-string
  --skill NAME        Skill identifier to update (for example: pick, explain)
  --score N           Satisfaction score from 1 to 5
  --date YYYY-MM-DD   Override current date for month/week period calculation
  --silent            Print only the structured result
  -h, --help          Show this help

Result tokens and exit status:
  UPDATED:<agent>/<model>:<skill>:<score>   exit 0
      The rating is recorded. <score> is the all-time average (0-100) every
      reader now shows, or the literal `unknown` when that total could not be
      read (stderr says why) -- the rating is recorded either way.
  STATS_ERROR:<reason>                      non-zero exit
      Nothing was recorded (for example: origin unreachable, no Python).
  Argument and registry errors print "Error: ..." and exit 1.
EOF
}

require_jq() {
    if ! command -v jq >/dev/null 2>&1; then
        die "jq is required. Install via your package manager."
    fi
}

parse_agent_string() {
    local agent_string="$1"

    if [[ ! "$agent_string" =~ ^([a-z]+)/([a-z0-9_]+)$ ]]; then
        die "Invalid agent string format: '$agent_string'. Expected <agent>/<model>."
    fi

    PARSED_AGENT="${BASH_REMATCH[1]}"
    PARSED_MODEL="${BASH_REMATCH[2]}"

    local agent
    for agent in "${SUPPORTED_AGENTS[@]}"; do
        if [[ "$agent" == "$PARSED_AGENT" ]]; then
            return
        fi
    done

    die "Unknown agent: '$PARSED_AGENT'. Supported: ${SUPPORTED_AGENTS[*]}"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent-string)
                [[ $# -lt 2 ]] && die "--agent-string requires a value"
                AGENT_STRING="$2"
                shift 2
                ;;
            --agent)
                [[ $# -lt 2 ]] && die "--agent requires a value"
                CLI_AGENT="$2"
                shift 2
                ;;
            --cli-id)
                [[ $# -lt 2 ]] && die "--cli-id requires a value"
                CLI_ID="$2"
                shift 2
                ;;
            --skill)
                [[ $# -lt 2 ]] && die "--skill requires a value"
                SKILL_NAME="$2"
                shift 2
                ;;
            --score)
                [[ $# -lt 2 ]] && die "--score requires a value"
                SCORE="$2"
                shift 2
                ;;
            --date)
                [[ $# -lt 2 ]] && die "--date requires a value"
                DATE_OVERRIDE="$2"
                shift 2
                ;;
            --silent)
                SILENT=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                die "Unknown argument: '$1'"
                ;;
        esac
    done

    [[ -n "$SKILL_NAME" ]] || die "--skill is required"
    [[ -n "$SCORE" ]] || die "--score is required"
    [[ "$SCORE" =~ ^[1-5]$ ]] || die "--score must be an integer from 1 to 5"

    # Mutual exclusion: --agent-string vs --agent/--cli-id
    if [[ -n "$AGENT_STRING" && ( -n "$CLI_AGENT" || -n "$CLI_ID" ) ]]; then
        die "--agent-string cannot be combined with --agent/--cli-id"
    fi

    if [[ -z "$AGENT_STRING" ]]; then
        # Must have both --agent and --cli-id
        [[ -n "$CLI_AGENT" ]] || die "Either --agent-string or --agent/--cli-id is required"
        [[ -n "$CLI_ID" ]] || die "--cli-id is required when --agent is provided"

        # Resolve via aitask_resolve_detected_agent.sh
        local resolve_output
        resolve_output="$("$SCRIPT_DIR/aitask_resolve_detected_agent.sh" --agent "$CLI_AGENT" --cli-id "$CLI_ID")"
        # Parse output: AGENT_STRING:<value> or AGENT_STRING_FALLBACK:<value>
        AGENT_STRING="${resolve_output#*:}"
    fi

    parse_agent_string "$AGENT_STRING"
}

models_file_for_agent() {
    local agent="$1"
    echo "aitasks/metadata/models_${agent}.json"
}

# Read-only: the registry decides which models exist; nothing here writes it.
ensure_model_exists() {
    local models_file="$1"
    local model_name="$2"

    if ! jq -e --arg model "$model_name" 'any(.models[]; .name == $model)' "$models_file" >/dev/null; then
        die "Model '$model_name' not found in $models_file — $(model_registration_hint "$PARSED_AGENT"), then re-run. Nothing was recorded."
    fi
}

main() {
    require_jq
    parse_args "$@"
    # The format only; the stats CLI rejects an impossible calendar date.
    if [[ -n "$DATE_OVERRIDE" && ! "$DATE_OVERRIDE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        die "--date must be in YYYY-MM-DD format"
    fi

    local models_file
    models_file="$(models_file_for_agent "$PARSED_AGENT")"
    [[ -f "$models_file" ]] || die "Model config not found: $models_file"

    ensure_model_exists "$models_file" "$PARSED_MODEL"

    local args=(--agent "$PARSED_AGENT" --model "$PARSED_MODEL" --skill "$SKILL_NAME" --score "$SCORE")
    [[ -n "$DATE_OVERRIDE" ]] && args+=(--date "$DATE_OVERRIDE")

    # Not in $( ): MODEL_STATS_LINE is an out-param, and the CLI's stderr must
    # reach ours.
    local write_rc=0
    model_stats_write record-verified "${args[@]}" || write_rc=$?
    if (( write_rc != 0 )); then
        if [[ "$SILENT" == "false" ]]; then
            warn "Verified score for ${AGENT_STRING} ${SKILL_NAME} was not recorded (${MODEL_STATS_LINE#STATS_ERROR:})."
        fi
        echo "$MODEL_STATS_LINE"
        return "$write_rc"
    fi

    # An integer, or `unknown`: recorded, but the current average is unavailable.
    local new_score="${MODEL_STATS_LINE##*:}"
    if [[ "$SILENT" == "false" ]]; then
        if [[ "$new_score" == "unknown" ]]; then
            success "Recorded ${AGENT_STRING} ${SKILL_NAME} rating (current average unavailable)"
        else
            success "Updated ${AGENT_STRING} ${SKILL_NAME} verified score to ${new_score}"
        fi
    fi
    echo "UPDATED:${AGENT_STRING}:${SKILL_NAME}:${new_score}"
}

main "$@"
