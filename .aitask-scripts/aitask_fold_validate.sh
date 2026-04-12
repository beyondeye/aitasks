#!/usr/bin/env bash
# aitask_fold_validate.sh - Validate fold candidate task IDs
#
# For each input ID, emits one structured output line:
#   VALID:<id>:<file_path>
#   INVALID:<id>:<reason>
# where <reason> is one of: not_found, is_self, has_children, status_<status>
#
# Callers parse the lines. Script always exits 0 (unless usage error).
#
# Usage: aitask_fold_validate.sh [--exclude-self <id>] <id1> [<id2> ...]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

usage() {
    cat <<EOF
Usage: $0 [--exclude-self <id>] <id1> [<id2> ...]

Validates each task ID as a fold candidate. IDs may be parent (e.g. 42) or
child (e.g. 16_2). Emits one line per ID:
  VALID:<id>:<path>
  INVALID:<id>:<reason>

Reasons: not_found, is_self, has_children, status_<status>

--exclude-self <id>   Mark the given ID as INVALID:<id>:is_self (for callers
                      that accept self-IDs in their input list).
EOF
    exit 1
}

exclude_self=""
ids=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --exclude-self)
            [[ $# -ge 2 ]] || die "--exclude-self requires an argument"
            exclude_self="${2#t}"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                ids+=("$1")
                shift
            done
            ;;
        -*)
            die "unknown flag: $1"
            ;;
        *)
            ids+=("$1")
            shift
            ;;
    esac
done

[[ ${#ids[@]} -eq 0 ]] && usage

for raw_id in "${ids[@]}"; do
    id="${raw_id#t}"

    if [[ -n "$exclude_self" && "$id" == "$exclude_self" ]]; then
        echo "INVALID:${id}:is_self"
        continue
    fi

    # Resolve the task file for parent or child IDs.
    file=""
    if [[ "$id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        parent="${BASH_REMATCH[1]}"
        child="${BASH_REMATCH[2]}"
        file=$(ls "$TASK_DIR"/t"${parent}"/t"${parent}"_"${child}"_*.md 2>/dev/null | head -1 || true)
    elif [[ "$id" =~ ^[0-9]+$ ]]; then
        file=$(ls "$TASK_DIR"/t"${id}"_*.md 2>/dev/null | head -1 || true)
    else
        echo "INVALID:${id}:not_found"
        continue
    fi

    if [[ -z "$file" ]]; then
        echo "INVALID:${id}:not_found"
        continue
    fi

    status=$(read_task_status "$file")
    if [[ "$status" != "Ready" && "$status" != "Editing" ]]; then
        echo "INVALID:${id}:status_${status}"
        continue
    fi

    # Parent IDs with pending children are not foldable.
    if [[ "$id" =~ ^[0-9]+$ ]]; then
        shopt -s nullglob
        child_matches=( "$TASK_DIR"/t"${id}"/*.md )
        shopt -u nullglob
        if [[ ${#child_matches[@]} -gt 0 ]]; then
            echo "INVALID:${id}:has_children"
            continue
        fi
    fi

    echo "VALID:${id}:${file}"
done
