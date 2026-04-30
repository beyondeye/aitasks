#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/verified_update_lib.sh"

SUPPORTED_AGENTS=(claudecode geminicli codex opencode)

AGENT_STRING=""
CLI_AGENT=""
CLI_ID=""
SKILL_NAME=""
SILENT=false
DATE_OVERRIDE=""

PARSED_AGENT=""
PARSED_MODEL=""
CURRENT_MONTH=""
CURRENT_WEEK=""
PREV_MONTH=""

show_help() {
    cat <<'EOF'
Usage: aitask_usage_update.sh [--agent-string <agent/model> | --agent <name> --cli-id <id>] --skill <skill> [--date YYYY-MM-DD] [--silent]

Increment rolling usage statistics (run counts only, no satisfaction score)
for a model/skill pair. Mirrors aitask_verified_update.sh but without --score
and without score_sum in any bucket.

Concurrency note:
  If the task data branch has a configured remote, the script uses a retrying
  remote-aware update flow to reduce lost updates from concurrent writers.
  Without a remote, it falls back to a local commit-only update and cannot
  guarantee protection against concurrent updates.

Options:
  --agent-string STR  Agent string in the form <agent>/<model>
  --agent NAME        Agent name (claudecode, geminicli, codex, opencode)
  --cli-id ID         Raw model ID from agent runtime (e.g. claude-opus-4-6)
                      Use --agent + --cli-id as alternative to --agent-string
  --skill NAME        Skill identifier to update (for example: pick, explain)
  --date YYYY-MM-DD   Override current date for month/week period calculation
  --silent            Print only the structured success result
  -h, --help          Show this help
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

resolve_date_periods() {
    if [[ -n "$DATE_OVERRIDE" ]]; then
        [[ "$DATE_OVERRIDE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] \
            || die "--date must be in YYYY-MM-DD format"
        CURRENT_MONTH="${DATE_OVERRIDE:0:7}"
        if date --version >/dev/null 2>&1; then
            CURRENT_WEEK="$(date -d "$DATE_OVERRIDE" "+%G-W%V")"
        else
            CURRENT_WEEK="$(date -j -f "%Y-%m-%d" "$DATE_OVERRIDE" "+%G-W%V")"
        fi
    else
        CURRENT_MONTH="$(date "+%Y-%m")"
        CURRENT_WEEK="$(date "+%G-W%V")"
    fi
    PREV_MONTH="$(previous_calendar_month "$CURRENT_MONTH")"
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
                die "--score is not accepted by aitask_usage_update.sh (use aitask_verified_update.sh for satisfaction-score updates)"
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

    if [[ -n "$AGENT_STRING" && ( -n "$CLI_AGENT" || -n "$CLI_ID" ) ]]; then
        die "--agent-string cannot be combined with --agent/--cli-id"
    fi

    if [[ -z "$AGENT_STRING" ]]; then
        [[ -n "$CLI_AGENT" ]] || die "Either --agent-string or --agent/--cli-id is required"
        [[ -n "$CLI_ID" ]] || die "--cli-id is required when --agent is provided"

        local resolve_output
        resolve_output="$("$SCRIPT_DIR/aitask_resolve_detected_agent.sh" --agent "$CLI_AGENT" --cli-id "$CLI_ID")"
        AGENT_STRING="${resolve_output#*:}"
    fi

    parse_agent_string "$AGENT_STRING"
}

models_file_for_agent() {
    local agent="$1"
    echo "aitasks/metadata/models_${agent}.json"
}

ensure_model_exists() {
    local models_file="$1"
    local model_name="$2"

    if ! jq -e --arg model "$model_name" 'any(.models[]; .name == $model)' "$models_file" >/dev/null; then
        die "Model '$model_name' not found in $models_file"
    fi
}

update_model_file() {
    local models_file="$1"
    local model_name="$2"
    local skill_name="$3"
    # $4 (extra) is unused — the shared lib forwards it for verified callers
    # which need raw_score; usage tracking has no score concept.

    local tmp_file
    tmp_file="$(mktemp "${TMPDIR:-/tmp}/aitask_usage_update.XXXXXX")"

    jq \
        --arg model "$model_name" \
        --arg skill "$skill_name" \
        --arg current_month "$CURRENT_MONTH" \
        --arg current_week "$CURRENT_WEEK" \
        --arg prev_month_target "$PREV_MONTH" '
        .models |= map(
            if .name == $model then
                .usagestats = (.usagestats // {}) |
                (
                    .usagestats[$skill] as $existing |
                    (
                        if ($existing | type) == "object" and ($existing | has("all_time")) then
                            $existing | (.prev_month //= {"period": "", "runs": 0})
                        else
                            {
                                "all_time":   {"runs": 0},
                                "prev_month": {"period": "", "runs": 0},
                                "month":      {"period": $current_month, "runs": 0},
                                "week":       {"period": $current_week,  "runs": 0}
                            }
                        end
                    ) as $base |
                    ($base.all_time.runs + 1) as $at_runs |
                    (if $base.month.period == $current_month then
                        $base.prev_month
                     elif $base.month.period == $prev_month_target then
                        $base.month
                     else
                        {"period": "", "runs": 0}
                     end) as $pm |
                    (if $base.month.period == $current_month then ($base.month.runs + 1) else 1 end) as $m_runs |
                    (if $base.week.period == $current_week then ($base.week.runs + 1) else 1 end) as $w_runs |
                    .usagestats[$skill] = {
                        "all_time":   {"runs": $at_runs},
                        "prev_month": $pm,
                        "month":      {"period": $current_month, "runs": $m_runs},
                        "week":       {"period": $current_week,  "runs": $w_runs}
                    }
                )
            else
                .
            end
        )
        ' "$models_file" > "$tmp_file"

    mv "$tmp_file" "$models_file"

    jq -r --arg model "$model_name" --arg skill "$skill_name" '
        .models[] | select(.name == $model) | .usagestats[$skill].month.runs
    ' "$models_file"
}

main() {
    require_jq
    parse_args "$@"
    resolve_date_periods

    local models_file
    models_file="$(models_file_for_agent "$PARSED_AGENT")"
    [[ -f "$models_file" ]] || die "Model config not found: $models_file"

    ensure_model_exists "$models_file" "$PARSED_MODEL"

    _AIT_UPDATE_MODEL_FILE_FN=update_model_file
    _AIT_COMMIT_PREFIX="ait: Update usage count"

    local new_runs
    if has_remote_tracking; then
        new_runs="$(commit_metadata_update "$models_file" "$AGENT_STRING" "$SKILL_NAME" "$PARSED_MODEL" "")"
    else
        if [[ "$SILENT" == "false" ]]; then
            warn "No remote configured for task data; using local-only usage update without concurrency protection."
        fi
        new_runs="$(update_model_file "$models_file" "$PARSED_MODEL" "$SKILL_NAME" "")"
        commit_metadata_update_local "$models_file" "$AGENT_STRING" "$SKILL_NAME"
    fi

    if [[ "$SILENT" == "false" ]]; then
        success "Updated ${AGENT_STRING} ${SKILL_NAME} usage count to ${new_runs}"
    fi
    echo "UPDATED:${AGENT_STRING}:${SKILL_NAME}:${new_runs}"
}

main "$@"
