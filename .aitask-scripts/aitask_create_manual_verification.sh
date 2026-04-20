#!/usr/bin/env bash
# aitask_create_manual_verification.sh - Create a manual-verification task with
# a seeded checklist. Wraps aitask_create.sh --batch and aitask_verification_parse.sh
# seed in one call. Used by planning.md (aggregate-sibling + single-task follow-up
# branches) and aitask-explore/SKILL.md.
#
# Usage:
#   aitask_create_manual_verification.sh \
#     --name <task_name> \
#     --verifies <csv_of_ids> \
#     --items <items_file> \
#     (--parent <parent_num> | --related <task_id>)
#
# Exit codes:
#   0 - success; stdout ends with MANUAL_VERIFICATION_CREATED:<new_id>:<new_path>
#   1 - usage error, file-not-found, or downstream script failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

NAME=""
VERIFIES=""
ITEMS=""
PARENT=""
RELATED=""
tmp_desc=""

show_help() {
    cat <<'EOF'
Usage: aitask_create_manual_verification.sh \
         --name <task_name> \
         --verifies <csv_of_ids> \
         --items <items_file> \
         (--parent <parent_num> | --related <task_id>)

Creates a manual-verification task (issue_type: manual_verification) with a
seeded "## Verification Checklist" populated from the items file. Exactly one
of --parent or --related must be specified:

  --parent <N>       aggregate-sibling mode: creates a child of parent N
  --related <id>     follow-up mode: creates a standalone task with --deps
                     <id> and a "Related to:" note in the body

Required:
  --name <name>      Task name slug (sanitized by aitask_create.sh)
  --verifies <csv>   Comma-separated list of task IDs this task verifies
  --items <path>     Path to a file with one checklist item per line

Structured output:
  MANUAL_VERIFICATION_CREATED:<new_id>:<path>   on success (exit 0)
  ERROR:<message>                               on failure (exit 1)
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --name)     NAME="$2"; shift 2 ;;
            --verifies) VERIFIES="$2"; shift 2 ;;
            --items)    ITEMS="$2"; shift 2 ;;
            --parent)   PARENT="$2"; shift 2 ;;
            --related)  RELATED="$2"; shift 2 ;;
            -h|--help)  show_help; exit 0 ;;
            *) die "Unknown argument: $1" ;;
        esac
    done
    [[ -n "$NAME" ]] || die "--name is required"
    [[ -n "$VERIFIES" ]] || die "--verifies is required"
    [[ -n "$ITEMS" ]] || die "--items is required"
    [[ -f "$ITEMS" ]] || die "Items file not found: $ITEMS"
    if [[ -n "$PARENT" && -n "$RELATED" ]]; then
        die "Specify either --parent or --related, not both"
    fi
    if [[ -z "$PARENT" && -z "$RELATED" ]]; then
        die "One of --parent or --related is required"
    fi
}

# Strip leading 't' from a task id (accepts both "t571_4" and "571_4").
strip_t_prefix() {
    echo "${1#t}"
}

main() {
    parse_args "$@"

    tmp_desc=$(mktemp "${TMPDIR:-/tmp}/mv_desc_XXXXXX.md")
    trap 'rm -f "${tmp_desc:-}"' EXIT

    # Build description body.
    {
        printf '## Manual Verification Task\n\n'
        printf 'This task is handled by the manual-verification module: run\n'
        # shellcheck disable=SC2016
        printf '`/aitask-pick <id>` and the workflow will dispatch to the\n'
        printf 'interactive checklist runner. Each item below must reach a\n'
        printf 'terminal state (Pass / Fail / Skip) before the task can be\n'
        printf 'archived; Defer is allowed but creates a carry-over task.\n\n'
        if [[ -n "$RELATED" ]]; then
            local bare_related; bare_related=$(strip_t_prefix "$RELATED")
            printf '**Related to:** t%s\n\n' "$bare_related"
        fi
        printf '## Verification Checklist\n'
    } > "$tmp_desc"

    # Compose aitask_create.sh invocation.
    local -a create_args=(
        --batch
        --type manual_verification
        --priority medium
        --effort medium
        --labels "verification,manual"
        --name "$NAME"
        --verifies "$VERIFIES"
        --desc-file "$tmp_desc"
        --commit
    )
    if [[ -n "$PARENT" ]]; then
        create_args+=(--parent "$PARENT")
    else
        local bare_related; bare_related=$(strip_t_prefix "$RELATED")
        create_args+=(--deps "$bare_related")
    fi

    # Run create; capture combined output so we can surface errors.
    local create_output
    if ! create_output=$("$SCRIPT_DIR/aitask_create.sh" "${create_args[@]}" 2>&1); then
        echo "ERROR:aitask_create.sh failed: $create_output"
        exit 1
    fi

    # Last non-empty line of output is the final "Created: <path>" line.
    local last_line new_path
    last_line=$(printf '%s\n' "$create_output" | awk 'NF { last = $0 } END { print last }')
    new_path="${last_line#Created: }"
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        echo "ERROR:could not parse created filepath from aitask_create.sh output: $last_line"
        exit 1
    fi

    # Parse the task id out of the basename (e.g., t583_10_foo.md -> 583_10).
    local new_basename new_id
    new_basename=$(basename "$new_path")
    new_id=$(echo "$new_basename" | sed -E 's/^t([0-9]+(_[0-9]+)?)_.*\.md$/\1/')
    if [[ -z "$new_id" || "$new_id" == "$new_basename" ]]; then
        echo "ERROR:could not parse task id from $new_path"
        exit 1
    fi

    # Seed the checklist into the newly created task.
    if ! "$SCRIPT_DIR/aitask_verification_parse.sh" seed "$new_path" --items "$ITEMS" >/dev/null 2>&1; then
        echo "ERROR:aitask_verification_parse.sh seed failed for $new_path"
        exit 1
    fi

    # Commit the seeded checklist (aitask_create.sh --commit only covered the
    # frontmatter + description body; the seed edited the file post-commit).
    ./ait git add "$new_path" >/dev/null 2>&1 || true
    ./ait git commit -m "ait: Seed verification checklist for t${new_id}" >/dev/null 2>&1 || true

    echo "MANUAL_VERIFICATION_CREATED:${new_id}:${new_path}"
}

main "$@"
