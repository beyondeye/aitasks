#!/usr/bin/env bash
# aitask_verification_followup.sh - Create a follow-up bug task from a failed
# manual-verification item. Pre-populates commits, touched files, and the
# verbatim failing item text, and back-references the origin feature task's
# archived plan (best-effort).
#
# Usage:
#   aitask_verification_followup.sh --from <task_id> --item <index> [--origin <feature_task_id>]
#
# Exit codes:
#   0 - success; stdout ends with FOLLOWUP_CREATED:<new_id>:<new_path>
#   1 - usage error, file-not-found, or aitask_create.sh failure
#   2 - ambiguous origin; stdout line ORIGIN_AMBIGUOUS:<csv> (no mutation)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

FROM_ID=""
ITEM_INDEX=""
ORIGIN=""
tmp=""

show_help() {
    cat <<'EOF'
Usage: aitask_verification_followup.sh --from <task_id> --item <index> [--origin <feature_task_id>]

Creates a follow-up bug task from a failed manual-verification item.

Required:
  --from <task_id>       ID of the manual-verification task (e.g., 571_7)
  --item <index>         1-indexed item number inside the task's
                         "## Verification Checklist" section

Optional:
  --origin <feature_id>  Feature task ID to attribute the failure to. Required
                         when the --from task's verifies: list has 2+ entries.

Structured output:
  FOLLOWUP_CREATED:<new_id>:<path>   on success (exit 0)
  ORIGIN_AMBIGUOUS:<csv>             when origin cannot be auto-resolved (exit 2)
  ERROR:<message>                    on failure (exit 1)
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --from)    FROM_ID="$2"; shift 2 ;;
            --item)    ITEM_INDEX="$2"; shift 2 ;;
            --origin)  ORIGIN="$2"; shift 2 ;;
            -h|--help) show_help; exit 0 ;;
            *) die "Unknown argument: $1" ;;
        esac
    done
    [[ -n "$FROM_ID" ]] || die "--from is required"
    [[ -n "$ITEM_INDEX" ]] || die "--item is required"
    [[ "$ITEM_INDEX" =~ ^[1-9][0-9]*$ ]] || die "--item must be a positive integer"
}

# Strip leading 't' from a task id (accepts both "t571_4" and "571_4").
strip_t_prefix() {
    local v="$1"
    echo "${v#t}"
}

# Extract the parent part of a task id: "571_4" -> "571", "571" -> "571".
parent_of() {
    local v="$1"
    if [[ "$v" == *_* ]]; then echo "${v%%_*}"; else echo "$v"; fi
}

# Locate the origin's archived plan file (tries child path first, then parent).
find_origin_archived_plan() {
    local origin="$1"
    local origin_parent; origin_parent=$(parent_of "$origin")
    local match=""
    # Child plan: aiplans/archived/p<parent>/p<origin>_*.md
    match=$(ls "aiplans/archived/p${origin_parent}/p${origin}_"*.md 2>/dev/null | head -n1 || true)
    if [[ -z "$match" ]]; then
        # Parent plan: aiplans/archived/p<origin>_*.md (no subdirectory)
        match=$(ls "aiplans/archived/p${origin}_"*.md 2>/dev/null | head -n1 || true)
    fi
    echo "$match"
}

main() {
    parse_args "$@"

    tmp=$(mktemp "${TMPDIR:-/tmp}/followup_XXXXXX.md")
    trap 'rm -f "${tmp:-}"' EXIT

    # Step 2: resolve source task file
    local from_file
    from_file=$(resolve_task_file "$FROM_ID")
    [[ -f "$from_file" ]] || die "Source task file not found: $from_file"

    # Step 3: extract failing item text via the parser
    local item_line
    item_line=$("$SCRIPT_DIR/aitask_verification_parse.sh" parse "$from_file" \
        | awk -F: -v idx="$ITEM_INDEX" '$1 == "ITEM" && $2 == idx { print; exit }')
    if [[ -z "$item_line" ]]; then
        echo "ERROR:item $ITEM_INDEX not found in $from_file"
        exit 1
    fi
    # parse output: ITEM:<idx>:<state>:<line>:<text>  -> everything after 4th colon
    local item_text
    item_text=$(echo "$item_line" | cut -d: -f5-)
    # Strip any existing " — STATE ..." annotation from a prior set.
    item_text="${item_text%% — *}"

    # Step 4: resolve origin
    local origin
    if [[ -n "$ORIGIN" ]]; then
        origin=$(strip_t_prefix "$ORIGIN")
    else
        local verifies_raw verifies_csv
        verifies_raw=$(read_yaml_field "$from_file" "verifies")
        verifies_csv=$(parse_yaml_list "$verifies_raw")
        if [[ -z "$verifies_csv" ]]; then
            origin=$(strip_t_prefix "$FROM_ID")
        elif [[ "$verifies_csv" != *","* ]]; then
            origin=$(strip_t_prefix "$verifies_csv")
        else
            echo "ORIGIN_AMBIGUOUS:$verifies_csv"
            exit 2
        fi
    fi

    # Step 5: resolve commits for origin (replicated detect_commits() one-liner)
    local commits
    commits=$(git log --oneline --all --grep="(t${origin})" 2>/dev/null || true)

    # Step 5b: locate origin's archived plan (for the Source section back-link)
    local origin_plan_for_doc
    origin_plan_for_doc=$(find_origin_archived_plan "$origin")

    # Step 6: resolve touched files
    local touched_files=""
    if [[ -n "$commits" ]]; then
        touched_files=$(
            printf '%s\n' "$commits" \
                | awk 'NF { print $1 }' \
                | while read -r h; do git show --name-only --format= "$h" 2>/dev/null; done \
                | sed '/^$/d' \
                | sort -u
        )
    fi

    # Step 7: compose description
    local bare_from_id_desc; bare_from_id_desc=$(strip_t_prefix "$FROM_ID")
    {
        printf '## Failed verification item from t%s\n\n' "$origin"
        printf '> %s\n\n' "$item_text"
        printf '### Source\n\n'
        printf -- '- **Manual-verification task:** `%s` (item #%s)\n' "$from_file" "$ITEM_INDEX"
        printf -- '- **Origin feature task:** t%s\n' "$origin"
        if [[ -n "$origin_plan_for_doc" ]]; then
            printf -- '- **Origin archived plan:** `%s`\n' "$origin_plan_for_doc"
        fi
        printf '\n### Commits that introduced the failing behavior\n\n'
        if [[ -n "$commits" ]]; then
            printf '%s\n' "$commits" | while IFS= read -r line; do
                [[ -z "$line" ]] && continue
                printf -- '- %s\n' "$line"
            done
        else
            printf -- '_(none detected — no commits matched (t%s))_\n' "$origin"
        fi
        printf '\n### Files touched by those commits\n\n'
        if [[ -n "$touched_files" ]]; then
            printf '%s\n' "$touched_files" | while IFS= read -r f; do
                [[ -z "$f" ]] && continue
                printf -- '- %s\n' "$f"
            done
        else
            printf -- '_(none)_\n'
        fi
        printf '\n### Next steps\n\n'
        printf 'Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. '
        printf 'This task was auto-generated from a manual-verification failure in t%s item #%s.\n' "$bare_from_id_desc" "$ITEM_INDEX"
    } > "$tmp"

    # Step 8: create the bug task
    # Derive a task name from the origin + item index. aitask_create.sh requires --name.
    local bare_from_id; bare_from_id=$(strip_t_prefix "$FROM_ID")
    local bug_name="fix_failed_verification_t${bare_from_id}_item${ITEM_INDEX}"
    local new_path
    if ! new_path=$("$SCRIPT_DIR/aitask_create.sh" --batch --silent \
            --type bug --priority medium --effort medium \
            --name "$bug_name" \
            --labels verification,bug \
            --deps "$origin" \
            --desc-file "$tmp" --commit 2>&1); then
        echo "ERROR:aitask_create.sh failed: $new_path"
        exit 1
    fi

    # aitask_create.sh --silent echoes just the filepath on success, but may emit
    # info lines during --commit. Take the last non-empty line as the filepath.
    new_path=$(printf '%s\n' "$new_path" | awk 'NF { last = $0 } END { print last }')

    local new_basename new_id
    new_basename=$(basename "$new_path")
    new_id=$(echo "$new_basename" | sed -E 's/^t([0-9]+(_[0-9]+)?)_.*\.md$/\1/')
    if [[ -z "$new_id" || "$new_id" == "$new_basename" ]]; then
        echo "ERROR:could not parse task id from $new_path"
        exit 1
    fi

    # Step 9: annotate the failing item in the source task
    "$SCRIPT_DIR/aitask_verification_parse.sh" set "$from_file" "$ITEM_INDEX" fail \
        --note "follow-up t${new_id}"

    # Step 10: back-reference origin's archived plan (best-effort, reuses Step 5b lookup)
    local origin_plan="$origin_plan_for_doc"
    if [[ -n "$origin_plan" && -f "$origin_plan" ]]; then
        local note
        note="- **Manual-verification failure:** item \"${item_text}\" failed; follow-up task t${new_id}."
        if grep -q '^## Final Implementation Notes' "$origin_plan" 2>/dev/null; then
            printf '%s\n' "$note" >> "$origin_plan"
        else
            printf '\n## Final Implementation Notes\n\n%s\n' "$note" >> "$origin_plan"
        fi
        ./ait git add "$origin_plan" 2>/dev/null || true
        ./ait git commit -m "ait: Back-reference manual-verification failure on t${origin}" 2>/dev/null || true
    fi

    # Step 11: structured success output
    echo "FOLLOWUP_CREATED:${new_id}:${new_path}"
}

main "$@"
