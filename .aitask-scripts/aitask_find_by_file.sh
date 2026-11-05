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
#   ./.aitask-scripts/aitask_find_by_file.sh [--project <name>] <path>
#
# Output:
#   TASK:<task_id>:<task_file>   one line per matching task
#
# Exit codes:
#   0  success (including no matches — output is silent)
#   1  argument error
#   2  file_references could not be read (no usable python/PyYAML, or a
#      read failure) -- never reported as "no matches"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/cross_repo_reexec.sh
source "$SCRIPT_DIR/lib/cross_repo_reexec.sh"

# Cross-repo redirect (t832_1): if `--project <name>` appears in argv,
# resolve <name> and re-exec the sibling's own aitask_find_by_file.sh in
# its root with `--project <name>` stripped. No-op when --project absent.
cross_repo_reexec_or_continue "aitask_find_by_file.sh" "$@"
if [[ ${#CROSS_REPO_FORWARDED_ARGV[@]} -gt 0 ]]; then
    set -- "${CROSS_REPO_FORWARDED_ARGV[@]}"
else
    set --
fi

TASK_DIR="${TASK_DIR:-aitasks}"

show_help() {
    cat <<'EOF'
Usage: aitask_find_by_file.sh [--project <name>] <path>

Find pending (Ready/Editing) tasks whose file_references frontmatter
list contains an entry for the given path.

Cross-repo:
  --project <name>    Re-exec the call inside the sibling aitasks project
                      <name> (resolved via the per-user registry at
                      ~/.config/aitasks/projects.yaml). Must appear before
                      the <path> argument.

Arguments:
  <path>    File path to search for. Matching is path-only: line
            ranges and compact multi-range specs (e.g., ":10-20^30-40")
            are stripped before comparison.

Output:
  TASK:<task_id>:<task_file>   one line per matching task

Exit codes:
  0   success (silent when no matches)
  1   missing or invalid argument
  2   file_references could not be read (no usable python/PyYAML)
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

# Is this task file a candidate? Ready/Editing only, and it must carry a
# `file_references:` key at all (a file without that line has no references,
# which is also the only set the pre-YAML reader could ever match).
is_candidate() {
    local file="$1" status
    [[ -f "$file" ]] || return 1
    status=$(read_task_status "$file")
    case "$status" in
        Ready|Editing) ;;
        *) return 1 ;;
    esac
    grep -q '^file_references:' "$file"
}

# Collect candidates: parent task files in $TASK_DIR (non-recursive, skip new/
# and archived/), then child task files one level deep -- the emit order.
candidates=()
shopt -s nullglob
for f in "$TASK_DIR"/t*.md; do
    if is_candidate "$f"; then candidates+=("$f"); fi
done
for d in "$TASK_DIR"/t*/; do
    [[ -d "$d" ]] || continue
    for f in "$d"t*_*.md; do
        if is_candidate "$f"; then candidates+=("$f"); fi
    done
done
shopt -u nullglob

[[ ${#candidates[@]} -gt 0 ]] || exit 0

# ONE YAML read for every candidate (lib/task_utils.sh). The field is read as
# YAML -- a quoted "a,b.py" is one path -- and a failed read is an error, never
# "no matches".
refs_rc=0
refs_out="$(read_file_references_batch "${candidates[@]}")" || refs_rc=$?
if [[ $refs_rc -ne 0 ]]; then
    reason="read failure"
    [[ $refs_rc -eq 3 ]] && reason="no usable python/PyYAML"
    echo "Error: could not read file_references (status $refs_rc: $reason)" >&2
    exit 2
fi

idx=-1
matched=false
warned=false
while IFS= read -r line; do
    case "$line" in
        FILE:*)
            idx="${line#FILE:}"; matched=false; warned=false ;;
        REF:*)
            [[ "$matched" == true ]] && continue
            entry="${line#REF:}"
            # Strip everything from the first ':' onward to get the path-only portion.
            if [[ "${entry%%:*}" == "$target_path" ]]; then
                file="${candidates[$idx]}"
                echo "TASK:$(extract_task_id "$file"):${file}"
                matched=true
            fi
            ;;
        BAD:*|INVALID:*)
            if [[ "$warned" == false ]]; then
                echo "Warning: ${candidates[$idx]}: file_references: is not a list of path strings; only its readable entries were matched" >&2
                warned=true
            fi
            ;;
    esac
done <<< "$refs_out"

exit 0
