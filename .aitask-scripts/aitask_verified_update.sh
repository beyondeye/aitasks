#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"

SUPPORTED_AGENTS=(claudecode geminicli codex opencode)

AGENT_STRING=""
SKILL_NAME=""
SCORE=""
SILENT=false

PARSED_AGENT=""
PARSED_MODEL=""

show_help() {
    cat <<'EOF'
Usage: aitask_verified_update.sh --agent-string <agent/model> --skill <skill> --score <1-5> [--silent]

Update rolling verification statistics for a model/skill pair.

Options:
  --agent-string STR  Agent string in the form <agent>/<model>
  --skill NAME        Skill identifier to update (for example: pick, explain)
  --score N           Satisfaction score from 1 to 5
  --silent            Print only the structured success result
  -h, --help          Show this help
EOF
}

require_jq() {
    command -v jq >/dev/null 2>&1 || die "jq is required. Install via your package manager."
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

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent-string)
                [[ $# -lt 2 ]] && die "--agent-string requires a value"
                AGENT_STRING="$2"
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

    [[ -n "$AGENT_STRING" ]] || die "--agent-string is required"
    [[ -n "$SKILL_NAME" ]] || die "--skill is required"
    [[ -n "$SCORE" ]] || die "--score is required"

    [[ "$SCORE" =~ ^[1-5]$ ]] || die "--score must be an integer from 1 to 5"

    parse_agent_string "$AGENT_STRING"
}

models_file_for_agent() {
    local agent="$1"
    echo "aitasks/metadata/models_${agent}.json"
}

ensure_model_exists() {
    local models_file="$1"
    local model_name="$2"

    jq -e --arg model "$model_name" 'any(.models[]; .name == $model)' "$models_file" >/dev/null \
        || die "Model '$model_name' not found in $models_file"
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
        --argjson mapped_score "$mapped_score" '
        .models |= map(
            if .name == $model then
                .verified = (.verified // {}) |
                .verifiedstats = (.verifiedstats // {}) |
                .verifiedstats[$skill] = {
                    "runs": ((.verifiedstats[$skill].runs // 0) + 1),
                    "score_sum": ((.verifiedstats[$skill].score_sum // 0) + $mapped_score)
                } |
                .verified[$skill] = ((.verifiedstats[$skill].score_sum / .verifiedstats[$skill].runs) | round)
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

commit_metadata_update() {
    local models_file="$1"
    local agent_string="$2"
    local skill_name="$3"

    ./ait git add "$models_file"

    if ./ait git diff --cached --quiet -- "$models_file"; then
        return
    fi

    if [[ "$SILENT" == "true" ]]; then
        ./ait git commit -m "ait: Update verified score for ${agent_string} ${skill_name}" >/dev/null
    else
        ./ait git commit -m "ait: Update verified score for ${agent_string} ${skill_name}"
    fi
}

main() {
    require_jq
    parse_args "$@"

    local models_file
    models_file="$(models_file_for_agent "$PARSED_AGENT")"
    [[ -f "$models_file" ]] || die "Model config not found: $models_file"

    ensure_model_exists "$models_file" "$PARSED_MODEL"

    local new_score
    new_score="$(update_model_file "$models_file" "$PARSED_MODEL" "$SKILL_NAME" "$SCORE")"

    commit_metadata_update "$models_file" "$AGENT_STRING" "$SKILL_NAME"

    if [[ "$SILENT" == "false" ]]; then
        success "Updated ${AGENT_STRING} ${SKILL_NAME} verified score to ${new_score}"
    fi
    echo "UPDATED:${AGENT_STRING}:${SKILL_NAME}:${new_score}"
}

main "$@"
