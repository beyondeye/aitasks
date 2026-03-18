#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/task_utils.sh"

SUPPORTED_AGENTS=(claudecode geminicli codex opencode)
MAX_REMOTE_RETRIES=5

AGENT_STRING=""
CLI_AGENT=""
CLI_ID=""
SKILL_NAME=""
SCORE=""
SILENT=false
DATE_OVERRIDE=""

PARSED_AGENT=""
PARSED_MODEL=""
CURRENT_MONTH=""
CURRENT_WEEK=""

show_help() {
    cat <<'EOF'
Usage: aitask_verified_update.sh [--agent-string <agent/model> | --agent <name> --cli-id <id>] --skill <skill> --score <1-5> [--date YYYY-MM-DD] [--silent]

Update rolling verification statistics for a model/skill pair.

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
  --score N           Satisfaction score from 1 to 5
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

log_info() {
    if [[ "$SILENT" == "false" ]]; then
        info "$@"
    fi
}

run_git_quiet() {
    if [[ "$SILENT" == "true" ]]; then
        "$@" >/dev/null 2>&1
    else
        "$@"
    fi
}

map_score() {
    local raw_score="$1"
    echo $((raw_score * 20))
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
    local raw_score="$4"
    local mapped_score
    mapped_score="$(map_score "$raw_score")"

    local tmp_file
    tmp_file="$(mktemp "${TMPDIR:-/tmp}/aitask_verified_update.XXXXXX")"

    jq \
        --arg model "$model_name" \
        --arg skill "$skill_name" \
        --argjson mapped_score "$mapped_score" \
        --arg current_month "$CURRENT_MONTH" \
        --arg current_week "$CURRENT_WEEK" '
        .models |= map(
            if .name == $model then
                .verified = (.verified // {}) |
                .verifiedstats = (.verifiedstats // {}) |
                (
                    .verifiedstats[$skill] as $existing |
                    (
                        if ($existing | type) == "object" and ($existing | has("runs")) and ($existing | has("all_time") | not) then
                            # Migrate old flat format to bucketed
                            {"all_time": {"runs": $existing.runs, "score_sum": $existing.score_sum}, "month": {"period": $current_month, "runs": 0, "score_sum": 0}, "week": {"period": $current_week, "runs": 0, "score_sum": 0}}
                        elif ($existing | type) == "object" and ($existing | has("all_time")) then
                            $existing
                        else
                            {"all_time": {"runs": 0, "score_sum": 0}, "month": {"period": $current_month, "runs": 0, "score_sum": 0}, "week": {"period": $current_week, "runs": 0, "score_sum": 0}}
                        end
                    ) as $base |
                    ($base.all_time.runs + 1) as $at_runs |
                    ($base.all_time.score_sum + $mapped_score) as $at_sum |
                    (if $base.month.period == $current_month then ($base.month.runs + 1) else 1 end) as $m_runs |
                    (if $base.month.period == $current_month then ($base.month.score_sum + $mapped_score) else $mapped_score end) as $m_sum |
                    (if $base.week.period == $current_week then ($base.week.runs + 1) else 1 end) as $w_runs |
                    (if $base.week.period == $current_week then ($base.week.score_sum + $mapped_score) else $mapped_score end) as $w_sum |
                    .verifiedstats[$skill] = {
                        "all_time": {"runs": $at_runs, "score_sum": $at_sum},
                        "month": {"period": $current_month, "runs": $m_runs, "score_sum": $m_sum},
                        "week": {"period": $current_week, "runs": $w_runs, "score_sum": $w_sum}
                    } |
                    .verified[$skill] = (($at_sum / $at_runs) | round)
                )
            else
                .
            end
        )
        ' "$models_file" > "$tmp_file"

    mv "$tmp_file" "$models_file"

    jq -r --arg model "$model_name" --arg skill "$skill_name" '
        .models[] | select(.name == $model) | .verified[$skill]
    ' "$models_file"
}

commit_metadata_update_local() {
    local models_file="$1"
    local agent_string="$2"
    local skill_name="$3"

    ./ait git add "$models_file"

    if ./ait git diff --cached --quiet -- "$models_file"; then
        return
    fi

    run_git_quiet ./ait git commit -m "ait: Update verified score for ${agent_string} ${skill_name}"
}

has_remote_tracking() {
    ./ait git remote get-url origin >/dev/null 2>&1 || return 1
    ./ait git rev-parse --abbrev-ref HEAD >/dev/null 2>&1 || return 1
}

current_task_branch() {
    ./ait git rev-parse --abbrev-ref HEAD
}

current_task_remote() {
    ./ait git remote get-url origin
}

configure_clone_identity() {
    local repo_dir="$1"
    local user_name=""
    local user_email=""

    user_name="$(./ait git config --get user.name 2>/dev/null || git config --global --get user.name 2>/dev/null || true)"
    user_email="$(./ait git config --get user.email 2>/dev/null || git config --global --get user.email 2>/dev/null || true)"

    if [[ -n "$user_name" ]]; then
        git -C "$repo_dir" config user.name "$user_name"
    fi
    if [[ -n "$user_email" ]]; then
        git -C "$repo_dir" config user.email "$user_email"
    fi
}

run_before_push_hook() {
    local repo_dir="$1"
    local attempt="$2"

    if [[ -z "${AITASK_VERIFIED_UPDATE_BEFORE_PUSH_HOOK:-}" ]]; then
        return 0
    fi

    AITASK_VERIFIED_UPDATE_ATTEMPT="$attempt" \
    AITASK_VERIFIED_UPDATE_TEMP_REPO="$repo_dir" \
        run_git_quiet bash "$AITASK_VERIFIED_UPDATE_BEFORE_PUSH_HOOK"
}

is_retryable_push_error() {
    local output="$1"
    printf '%s' "$output" | grep -Eq 'non-fast-forward|fetch first|rejected|failed to push some refs'
}

sync_current_repo_from_remote() {
    task_sync
}

commit_and_push_from_remote_clone() {
    local models_file="$1"
    local agent_string="$2"
    local skill_name="$3"
    local model_name="$4"
    local branch="$5"
    local remote_url="$6"
    local attempt="$7"

    local tmpdir clone_dir new_score push_output
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/aitask_verified_remote.XXXXXX")"
    clone_dir="$tmpdir/repo"

    if ! run_git_quiet git clone --quiet --branch "$branch" --single-branch "$remote_url" "$clone_dir"; then
        rm -rf "$tmpdir"
        die "Failed to clone task data branch '$branch' from origin"
    fi

    configure_clone_identity "$clone_dir"

    ensure_model_exists "$clone_dir/$models_file" "$model_name"
    new_score="$(update_model_file "$clone_dir/$models_file" "$model_name" "$skill_name" "$SCORE")"

    git -C "$clone_dir" add "$models_file"
    if git -C "$clone_dir" diff --cached --quiet -- "$models_file"; then
        rm -rf "$tmpdir"
        echo "$new_score"
        return 0
    fi

    if ! run_git_quiet git -C "$clone_dir" commit -m "ait: Update verified score for ${agent_string} ${skill_name}"; then
        rm -rf "$tmpdir"
        die "Failed to commit verified score update"
    fi

    run_before_push_hook "$clone_dir" "$attempt"

    if push_output="$(git -C "$clone_dir" push --quiet origin "HEAD:${branch}" 2>&1)"; then
        rm -rf "$tmpdir"
        sync_current_repo_from_remote
        echo "$new_score"
        return 0
    fi

    rm -rf "$tmpdir"

    if is_retryable_push_error "$push_output"; then
        log_info "Verified score update raced with another push; retrying (${attempt}/${MAX_REMOTE_RETRIES})"
        return 10
    fi

    die "Failed to push verified score update: $push_output"
}

commit_metadata_update() {
    local models_file="$1"
    local agent_string="$2"
    local skill_name="$3"
    local model_name="$4"

    if ! has_remote_tracking; then
        commit_metadata_update_local "$models_file" "$agent_string" "$skill_name"
        return 0
    fi

    local branch remote_url attempt new_score rc
    branch="$(current_task_branch)"
    remote_url="$(current_task_remote)"

    for attempt in $(seq 1 "$MAX_REMOTE_RETRIES"); do
        set +e
        new_score="$(commit_and_push_from_remote_clone "$models_file" "$agent_string" "$skill_name" "$model_name" "$branch" "$remote_url" "$attempt")"
        rc=$?
        set -e

        if [[ $rc -eq 0 ]]; then
            printf '%s\n' "$new_score"
            return 0
        fi
        if [[ $rc -ne 10 ]]; then
            return "$rc"
        fi
    done

    die "Failed to update verified score after ${MAX_REMOTE_RETRIES} retries due to concurrent pushes"
}

main() {
    require_jq
    parse_args "$@"
    resolve_date_periods

    local models_file
    models_file="$(models_file_for_agent "$PARSED_AGENT")"
    [[ -f "$models_file" ]] || die "Model config not found: $models_file"

    ensure_model_exists "$models_file" "$PARSED_MODEL"

    local new_score
    if has_remote_tracking; then
        new_score="$(commit_metadata_update "$models_file" "$AGENT_STRING" "$SKILL_NAME" "$PARSED_MODEL")"
    else
        if [[ "$SILENT" == "false" ]]; then
            warn "No remote configured for task data; using local-only verified score update without concurrency protection."
        fi
        new_score="$(update_model_file "$models_file" "$PARSED_MODEL" "$SKILL_NAME" "$SCORE")"
        commit_metadata_update_local "$models_file" "$AGENT_STRING" "$SKILL_NAME"
    fi

    if [[ "$SILENT" == "false" ]]; then
        success "Updated ${AGENT_STRING} ${SKILL_NAME} verified score to ${new_score}"
    fi
    echo "UPDATED:${AGENT_STRING}:${SKILL_NAME}:${new_score}"
}

main "$@"
