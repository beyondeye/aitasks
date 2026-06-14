#!/usr/bin/env bash
# aitask_shadow_context.sh - Fetch task/plan context for the shadow agent.
#
# Thin orchestrator over aitask_query_files.sh. Given a source task id (the task
# a followed coding agent is working on), emit the task file path, the
# most-recent plan path, and optionally sibling context. Used by the shadow
# skill (t986_4) for use-case 2: an AskUserQuestion shown in the terminal
# without its source task/plan visible (e.g. a session working "t635_3").
#
# Usage:
#   ./.aitask-scripts/aitask_shadow_context.sh [--siblings] <task_id>
#
#   <task_id>     N, tN, N_M, or tN_M (optional leading "t" is stripped)
#   --siblings    Also emit sibling context (default off, to stay cheap)
#
# Output (stdout; all resolution outcomes exit 0 - parse the lines, not the
# exit code, mirroring aitask_query_files.sh):
#   TASK_FILE:<path>   or TASK_FILE:NOT_FOUND
#   PLAN_FILE:<path>   or PLAN_FILE:NOT_FOUND   (active plan; most-recent if many)
#   SIBLING:<path>     zero or more lines, only with --siblings
#
# A malformed id is the one hard error (die, non-zero exit).
#
# Scope: active task -> active plan is the primary path (a followed agent is
# working the task, so its plan lives in aiplans/). Archived TASK files are
# resolved as a fallback, but archived/historical PLAN retrieval is the job of
# aitask_explain_context.sh (on demand) - this helper deliberately stays thin
# and emits PLAN_FILE:NOT_FOUND rather than scanning the archive. It builds no
# parallel cache and forks no scan logic.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

QUERY="$SCRIPT_DIR/aitask_query_files.sh"

show_help() {
    cat <<'EOF'
Usage: aitask_shadow_context.sh [--siblings] <task_id>

Fetch task/plan context for the shadow agent (thin wrapper over
aitask_query_files.sh).

Arguments:
  <task_id>     N, tN, N_M, or tN_M
  --siblings    Also emit sibling context (default off)

Output lines:
  TASK_FILE:<path>   or TASK_FILE:NOT_FOUND
  PLAN_FILE:<path>   or PLAN_FILE:NOT_FOUND
  SIBLING:<path>     zero or more (only with --siblings)
EOF
}

# --- Argument parsing ---
siblings=false
task_id=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --siblings) siblings=true; shift ;;
        -h|--help)  show_help; exit 0 ;;
        -*)         die "Unknown option: $1" ;;
        *)
            [[ -z "$task_id" ]] || die "Unexpected extra argument: $1"
            task_id="$1"; shift ;;
    esac
done

[[ -n "$task_id" ]] || { show_help >&2; die "task_id required"; }

# Strip optional leading "t" and classify parent vs child.
id="${task_id#t}"
if [[ "$id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
    is_child=true
    parent="${BASH_REMATCH[1]}"
    child="${BASH_REMATCH[2]}"
elif [[ "$id" =~ ^[0-9]+$ ]]; then
    is_child=false
    parent="$id"
else
    die "Invalid task id: '$task_id' (expected N, tN, N_M, or tN_M)"
fi

# --- Resolve task file (active first, then archived) ---
# Echoes the resolved path, or "NOT_FOUND".
resolve_task_file() {
    local out
    if [[ "$is_child" == true ]]; then
        out=$("$QUERY" child-file "$parent" "$child")
        if [[ "$out" == CHILD_FILE:* ]]; then
            printf '%s\n' "${out#CHILD_FILE:}"
            return
        fi
        out=$("$QUERY" archived-task "${parent}_${child}")
    else
        out=$("$QUERY" task-file "$parent")
        if [[ "$out" == TASK_FILE:* ]]; then
            printf '%s\n' "${out#TASK_FILE:}"
            return
        fi
        out=$("$QUERY" archived-task "$parent")
    fi

    case "$out" in
        ARCHIVED_TASK_ARCHIVE:*) printf '%s\n' "${out#ARCHIVED_TASK_ARCHIVE:}" ;;
        ARCHIVED_TASK:*)         printf '%s\n' "${out#ARCHIVED_TASK:}" ;;
        *)                       printf '%s\n' "NOT_FOUND" ;;
    esac
}

task_path=$(resolve_task_file)
if [[ "$task_path" == "NOT_FOUND" ]]; then
    echo "TASK_FILE:NOT_FOUND"
else
    echo "TASK_FILE:$task_path"
fi

# --- Resolve most-recent active plan ---
# plan-file handles both parent (p<N>_*.md) and child (p<N>/p<N>_<M>_*.md).
# When several match, take the lexicographically-last (ls-sorted) path.
plan_out=$("$QUERY" plan-file "$id")
if [[ "$plan_out" == PLAN_FILE:* ]]; then
    plan_path=$(printf '%s\n' "${plan_out#PLAN_FILE:}" | tail -n1)
    echo "PLAN_FILE:$plan_path"
else
    echo "PLAN_FILE:NOT_FOUND"
fi

# --- Optional sibling context ---
if [[ "$siblings" == true ]]; then
    sib_out=$("$QUERY" sibling-context "$parent")
    if [[ "$sib_out" != "NO_CONTEXT" ]]; then
        while IFS= read -r line; do
            [[ -n "$line" ]] || continue
            [[ "$line" == "NO_CONTEXT" ]] && continue
            # Strip the query_files sub-type prefix (ARCHIVED_PLAN:/ARCHIVED_TASK:
            # /PENDING_SIBLING:/PENDING_PLAN:) down to the bare path.
            printf 'SIBLING:%s\n' "${line#*:}"
        done <<< "$sib_out"
    fi
fi
