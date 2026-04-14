#!/usr/bin/env bash
# aitask_plan_externalize.sh - Externalize a Claude Code internal plan file
# to the project's aiplans/ directory.
#
# Claude Code's EnterPlanMode writes the approved plan to an internal file
# at ~/.claude/plans/<random>.md. This script copies it to the canonical
# external path (aiplans/p<N>_<stem>.md for parent tasks, or
# aiplans/p<parent>/p<parent>_<child>_<stem>.md for child tasks) and
# prepends the required metadata header when missing.
#
# Usage:
#   aitask_plan_externalize.sh <task_id> [--internal <path>] [--force]
#
# Arguments:
#   <task_id>            Task number (e.g. 16, t16) or child id (e.g. 16_2)
#   --internal <path>    Explicit internal plan file path (skips scan)
#   --force              Overwrite an existing external plan file
#                        (default: no-op, emits PLAN_EXISTS)
#
# Environment:
#   AIT_PLAN_EXTERNALIZE_INTERNAL_DIR   Override internal plans dir
#                                        (default: ~/.claude/plans)
#   AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS   Max age for auto-discovered files
#                                        (default: 3600)
#
# Output lines (exit 0):
#   PLAN_EXISTS:<external_path>
#   EXTERNALIZED:<external_path>:<source>
#   OVERWRITTEN:<external_path>:<source>
#   MULTIPLE_CANDIDATES:<path1>|<path2>|...
#   NOT_FOUND:<reason>
#
# Reasons for NOT_FOUND:
#   no_internal_dir      ~/.claude/plans/ does not exist
#   no_internal_files    Directory empty or no files within age window
#   source_not_file      --internal path missing or not a regular file
#   no_task_file         Cannot resolve <task_id> to a task filename
#
# Encapsulation: SKILL.md should never mention ~/.claude/plans, mtime
# filtering, or internal plan file details. Those concerns live here.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

TASK_DIR="${TASK_DIR:-aitasks}"
PLAN_DIR="${PLAN_DIR:-aiplans}"
ARCHIVED_PLAN_DIR="${ARCHIVED_PLAN_DIR:-aiplans/archived}"

INTERNAL_PLANS_DIR="${AIT_PLAN_EXTERNALIZE_INTERNAL_DIR:-$HOME/.claude/plans}"
MAX_AGE_SECS="${AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS:-3600}"

usage() {
    cat <<'EOF'
Usage: aitask_plan_externalize.sh <task_id> [--internal <path>] [--force]

Externalize a Claude Code internal plan file to aiplans/.

Arguments:
  <task_id>            Task number (e.g. 16, t16) or child id (e.g. 16_2)
  --internal <path>    Explicit internal plan file path (skips auto-scan)
  --force              Overwrite an existing external plan file
                       (default: no-op, emits PLAN_EXISTS)

Output (exit 0):
  PLAN_EXISTS:<path>                  Already externalized (no-op)
  EXTERNALIZED:<path>:<source>        Copied successfully
  OVERWRITTEN:<path>:<source>         Existing file replaced (--force)
  MULTIPLE_CANDIDATES:<p1>|<p2>|...   Ambiguous; caller disambiguates
  NOT_FOUND:<reason>                  Could not externalize
EOF
}

# --- Arg parsing ---

TASK_ID=""
INTERNAL_OVERRIDE=""
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --internal)
            [[ $# -ge 2 ]] || die "--internal requires a path argument"
            INTERNAL_OVERRIDE="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        -*)
            die "Unknown flag: $1"
            ;;
        *)
            [[ -n "$TASK_ID" ]] && die "Unexpected extra argument: $1"
            TASK_ID="$1"
            shift
            ;;
    esac
done

[[ -n "$TASK_ID" ]] || { usage >&2; die "Missing <task_id> argument"; }

TASK_ID="${TASK_ID#t}"
TASK_ID="${TASK_ID#p}"

# --- Resolve task file + compute external plan path ---

PARENT_NUM=""
CHILD_NUM=""
IS_CHILD=false

if [[ "$TASK_ID" =~ ^([0-9]+)_([0-9]+)$ ]]; then
    PARENT_NUM="${BASH_REMATCH[1]}"
    CHILD_NUM="${BASH_REMATCH[2]}"
    IS_CHILD=true
elif [[ "$TASK_ID" =~ ^[0-9]+$ ]]; then
    PARENT_NUM="$TASK_ID"
else
    die "Invalid task id: '$TASK_ID' (expected N or N_M)"
fi

TASK_FILE=""
if [[ "$IS_CHILD" == true ]]; then
    for f in "$TASK_DIR"/t"${PARENT_NUM}"/t"${PARENT_NUM}"_"${CHILD_NUM}"_*.md; do
        [[ -e "$f" ]] || continue
        TASK_FILE="$f"
        break
    done
else
    for f in "$TASK_DIR"/t"${PARENT_NUM}"_*.md; do
        [[ -e "$f" ]] || continue
        TASK_FILE="$f"
        break
    done
fi

if [[ -z "$TASK_FILE" ]]; then
    echo "NOT_FOUND:no_task_file"
    exit 0
fi

TASK_BASENAME=$(basename "$TASK_FILE")
PLAN_BASENAME="p${TASK_BASENAME#t}"

if [[ "$IS_CHILD" == true ]]; then
    EXTERNAL_PLAN="$PLAN_DIR/p${PARENT_NUM}/${PLAN_BASENAME}"
else
    EXTERNAL_PLAN="$PLAN_DIR/${PLAN_BASENAME}"
fi

# --- No-op if already externalized (unless --force) ---

EXISTED_BEFORE=false
if [[ -f "$EXTERNAL_PLAN" ]]; then
    if [[ "$FORCE" != true ]]; then
        echo "PLAN_EXISTS:$EXTERNAL_PLAN"
        exit 0
    fi
    EXISTED_BEFORE=true
fi

# --- Locate source internal plan ---

SOURCE=""

if [[ -n "$INTERNAL_OVERRIDE" ]]; then
    if [[ ! -f "$INTERNAL_OVERRIDE" ]]; then
        echo "NOT_FOUND:source_not_file"
        exit 0
    fi
    SOURCE="$INTERNAL_OVERRIDE"
else
    if [[ ! -d "$INTERNAL_PLANS_DIR" ]]; then
        echo "NOT_FOUND:no_internal_dir"
        exit 0
    fi

    get_mtime() {
        local f="$1"
        local m
        if m=$(stat -c %Y "$f" 2>/dev/null); then
            echo "$m"
        elif m=$(stat -f %m "$f" 2>/dev/null); then
            echo "$m"
        else
            echo ""
        fi
    }

    now=$(date +%s)
    cutoff=$(( now - MAX_AGE_SECS ))

    candidates=()
    shopt -s nullglob
    for f in "$INTERNAL_PLANS_DIR"/*.md; do
        [[ -f "$f" ]] || continue
        mt=$(get_mtime "$f")
        [[ -n "$mt" ]] || continue
        if (( mt >= cutoff )); then
            candidates+=("${mt}|${f}")
        fi
    done
    shopt -u nullglob

    if [[ ${#candidates[@]} -eq 0 ]]; then
        echo "NOT_FOUND:no_internal_files"
        exit 0
    fi

    if [[ ${#candidates[@]} -gt 1 ]]; then
        sorted=$(printf '%s\n' "${candidates[@]}" | sort -t'|' -k1,1nr)
        paths=()
        while IFS='|' read -r _ p; do
            paths+=("$p")
        done <<< "$sorted"
        joined=""
        for p in "${paths[@]}"; do
            if [[ -n "$joined" ]]; then
                joined="${joined}|${p}"
            else
                joined="$p"
            fi
        done
        echo "MULTIPLE_CANDIDATES:$joined"
        exit 0
    fi

    SOURCE="${candidates[0]#*|}"
fi

# --- Build external plan file with metadata header if missing ---

mkdir -p "$(dirname "$EXTERNAL_PLAN")"

has_frontmatter=false
first_line=$(head -n 1 "$SOURCE" 2>/dev/null || true)
if [[ "$first_line" == "---" ]]; then
    has_frontmatter=true
fi

build_header() {
    local current_branch=""
    current_branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "")

    echo "---"
    echo "Task: $TASK_BASENAME"

    if [[ "$IS_CHILD" == true ]]; then
        local parent_file=""
        for f in "$TASK_DIR"/t"${PARENT_NUM}"_*.md; do
            [[ -e "$f" ]] || continue
            parent_file="$f"
            break
        done
        [[ -n "$parent_file" ]] && echo "Parent Task: $parent_file"

        local siblings=()
        for f in "$TASK_DIR"/t"${PARENT_NUM}"/t"${PARENT_NUM}"_*_*.md; do
            [[ -e "$f" ]] || continue
            [[ "$f" == "$TASK_FILE" ]] && continue
            siblings+=("$f")
        done
        if [[ ${#siblings[@]} -gt 0 ]]; then
            local joined=""
            for s in "${siblings[@]}"; do
                if [[ -n "$joined" ]]; then
                    joined="${joined}, ${s}"
                else
                    joined="$s"
                fi
            done
            echo "Sibling Tasks: $joined"
        fi

        local archived_plans=()
        for f in "$ARCHIVED_PLAN_DIR"/p"${PARENT_NUM}"/p"${PARENT_NUM}"_*_*.md; do
            [[ -e "$f" ]] || continue
            archived_plans+=("$f")
        done
        if [[ ${#archived_plans[@]} -gt 0 ]]; then
            local joined=""
            for s in "${archived_plans[@]}"; do
                if [[ -n "$joined" ]]; then
                    joined="${joined}, ${s}"
                else
                    joined="$s"
                fi
            done
            echo "Archived Sibling Plans: $joined"
        fi
    fi

    local task_name="${TASK_BASENAME%.md}"
    [[ -d "aiwork/${task_name}" ]] && echo "Worktree: aiwork/${task_name}"

    if [[ -n "$current_branch" && "$current_branch" != "main" ]]; then
        echo "Branch: $current_branch"
    fi

    echo "Base branch: main"
    echo "---"
    echo ""
}

tmp_target=$(mktemp "${TMPDIR:-/tmp}/ait_externalize_XXXXXX.md")

if [[ "$has_frontmatter" == true ]]; then
    cat "$SOURCE" > "$tmp_target"
else
    {
        build_header
        cat "$SOURCE"
    } > "$tmp_target"
fi

mv "$tmp_target" "$EXTERNAL_PLAN"

if [[ "$EXISTED_BEFORE" == true ]]; then
    echo "OVERWRITTEN:${EXTERNAL_PLAN}:${SOURCE}"
else
    echo "EXTERNALIZED:${EXTERNAL_PLAN}:${SOURCE}"
fi
