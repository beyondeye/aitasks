#!/usr/bin/env bash
# aitask_find_by_file.sh - List pending tasks that reference a given file path
#
# Scans active task files (parents in aitasks/ and children in aitasks/t*/)
# and emits one structured line per match. Only tasks with status Ready or
# Editing are returned; archived and in-flight tasks (Implementing/Postponed/
# Done/Folded) are excluded.
#
# Matching is path-only: a task entry "foo.py", "foo.py:10-20", or
# "foo.py:10-20^30-40^89-100" all count as a match for path "foo.py".
#
# Usage:
#   ./.aitask-scripts/aitask_find_by_file.sh <path>
#
# Output:
#   TASK:<task_id>:<task_file>   one line per matching task
#
# Exit codes:
#   0  success (including no matches — output is silent)
#   1  argument error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

TASK_DIR="${TASK_DIR:-aitasks}"

show_help() {
    cat <<'EOF'
Usage: aitask_find_by_file.sh <path>

Find pending (Ready/Editing) tasks whose file_references frontmatter
list contains an entry for the given path.

Arguments:
  <path>    File path to search for. Matching is path-only: line
            ranges and compact multi-range specs (e.g., ":10-20^30-40")
            are stripped before comparison.

Output:
  TASK:<task_id>:<task_file>   one line per matching task

Exit codes:
  0   success (silent when no matches)
  1   missing or invalid argument
EOF
}

if [[ $# -lt 1 ]]; then
    show_help >&2
    die "Missing required argument: <path>"
fi

case "$1" in
    -h|--help) show_help; exit 0 ;;
esac

target_path="$1"
if [[ -z "$target_path" ]]; then
    die "Empty path argument"
fi

# Extract task id from a file path like "aitasks/t42_name.md" or
# "aitasks/t42/t42_3_name.md". Output: "42" or "42_3".
extract_task_id() {
    local file="$1"
    local base
    base=$(basename "$file" .md)
    # Strip leading 't' and trailing _<name>
    echo "$base" | sed -E 's/^t([0-9]+(_[0-9]+)?)_.*$/\1/'
}

# For a task file, check whether its file_references contain an entry
# whose path-only portion equals the target. Emit a TASK: line on match.
check_task_file() {
    local file="$1"
    [[ -f "$file" ]] || return 0

    local status
    status=$(read_task_status "$file")
    case "$status" in
        Ready|Editing) ;;
        *) return 0 ;;
    esac

    local entry entry_path
    while IFS= read -r entry; do
        [[ -z "$entry" ]] && continue
        # Strip everything from the first ':' onward to get the path-only portion.
        entry_path="${entry%%:*}"
        if [[ "$entry_path" == "$target_path" ]]; then
            local task_id
            task_id=$(extract_task_id "$file")
            echo "TASK:${task_id}:${file}"
            return 0
        fi
    done < <(get_file_references "$file")
}

# Scan parent task files in $TASK_DIR (non-recursive, skip new/ and archived/).
shopt -s nullglob
for f in "$TASK_DIR"/t*.md; do
    check_task_file "$f"
done

# Scan child task files in $TASK_DIR/t*/ (one level deep).
for d in "$TASK_DIR"/t*/; do
    [[ -d "$d" ]] || continue
    for f in "$d"t*_*.md; do
        check_task_file "$f"
    done
done
shopt -u nullglob

exit 0
