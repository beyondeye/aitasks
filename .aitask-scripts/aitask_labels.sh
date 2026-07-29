#!/usr/bin/env bash
# aitask_labels.sh - Label vocabulary queries for skills and TUIs.
#
# Deterministic, unit-testable front end over the label seam in
# lib/task_utils.sh (sanitize_label / get_existing_labels). Used by the
# /aitask-explore label-confirmation step to tell the agent which of its
# proposed labels already exist, which are near-duplicates of an existing
# label, and which would mint a genuinely new vocabulary entry.
#
# It is READ-ONLY: it never writes aitasks/metadata/labels.txt. Vocabulary
# growth happens at task-creation time (aitask_create.sh --batch), so the new
# label and the task that uses it land in one commit.
#
# Usage:
#   aitask_labels.sh list
#   aitask_labels.sh classify "<csv>"
#
# Output — `list` (one line per vocabulary entry, in file order):
#   LABEL:<name>
#
# Output — `classify` (one line per proposed label, in input order):
#   EXISTING:<sanitized>                     already in the vocabulary
#   NEAR:<sanitized>:<existing1>,<existing2> not present, but separator/case
#                                            variants of it are
#   NEW:<sanitized>                          would mint a new entry
#   INVALID:<original>                       sanitizes to nothing; unusable
#
# "Near" match = equal after stripping to [a-z0-9], so `aitask-create` and
# `aitask_create` are near-duplicates of each other. Typo variants
# (`brainstom_modules` vs `brainstorm_modules`) are NOT matched — see the
# label_fuzzy_match_typos follow-up.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

usage() {
    cat <<'EOF'
Usage:
  aitask_labels.sh list                Print the label vocabulary
  aitask_labels.sh classify "<csv>"    Classify proposed labels against it

Classify emits one line per proposed label, in input order:
  EXISTING:<label> | NEAR:<label>:<candidates> | NEW:<label> | INVALID:<orig>
EOF
}

# Comparison key for near-duplicate detection: drop every separator so
# "aitask-create" and "aitask_create" collapse to the same key.
_label_key() {
    printf '%s' "$1" | tr -d '_-'
}

cmd_list() {
    local label
    while IFS= read -r label; do
        [[ -z "$label" ]] && continue
        echo "LABEL:$label"
    done < <(get_existing_labels)
}

cmd_classify() {
    local csv="${1:-}"
    local -a existing=() parts=()
    local label raw trimmed clean key cand_key
    local -a candidates=()

    while IFS= read -r label; do
        [[ -z "$label" ]] && continue
        existing+=("$label")
    done < <(get_existing_labels)

    [[ -z "$csv" ]] && return 0
    IFS=',' read -ra parts <<< "$csv"

    for raw in "${parts[@]}"; do
        trimmed="${raw#"${raw%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [[ -z "$trimmed" ]] && continue

        clean=$(sanitize_label "$trimmed")
        if [[ -z "$clean" ]]; then
            echo "INVALID:$trimmed"
            continue
        fi

        local found=false
        for label in ${existing[@]+"${existing[@]}"}; do
            [[ "$label" == "$clean" ]] && { found=true; break; }
        done
        if [[ "$found" == true ]]; then
            echo "EXISTING:$clean"
            continue
        fi

        key=$(_label_key "$clean")
        candidates=()
        for label in ${existing[@]+"${existing[@]}"}; do
            cand_key=$(_label_key "$label")
            [[ "$cand_key" == "$key" ]] && candidates+=("$label")
        done

        if (( ${#candidates[@]} > 0 )); then
            echo "NEAR:$clean:$(IFS=','; printf '%s' "${candidates[*]}")"
        else
            echo "NEW:$clean"
        fi
    done
}

main() {
    local subcommand="${1:-}"
    case "$subcommand" in
        list)
            cmd_list
            ;;
        classify)
            shift || true
            cmd_classify "${1:-}"
            ;;
        -h|--help|"")
            usage
            [[ -z "$subcommand" ]] && exit 1
            exit 0
            ;;
        *)
            usage >&2
            die "unknown subcommand: $subcommand"
            ;;
    esac
}

main "$@"
