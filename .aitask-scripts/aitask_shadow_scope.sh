#!/usr/bin/env bash
# aitask_shadow_scope.sh - Ownership EVIDENCE for the shadow's implementation review.
#
# Reports, for every changed file part in the followed agent's checkout, the
# evidence bearing on whether it is the followed task's change: the task's own
# tagged commits, plan / task-description references (with the section they
# appear under), the claim-time baseline, and other active tasks' claims. It
# NEVER decides ownership -- the shadow reads the changes and judges
# (.claude/skills/aitask-shadow/impl-challenge.md, "Ownership judgement").
# The evidence assembly lives in lib/shadow_scope.py; this wrapper only resolves
# WHICH checkout to inspect.
#
# Usage:
#   ./.aitask-scripts/aitask_shadow_scope.sh <task_id> [--checkout <dir>]
#
#   <task_id>          N, tN, N_M, or tN_M
#   --checkout <dir>   inspect this checkout instead of resolving one
#
# Checkout resolution (first hit wins; reported as CHECKOUT:<abs>|<source>):
#   1. --checkout                                  explicit
#   2. the task's registered worktree              worktree_record
#      (aitask_task_worktree.sh resolve -> USABLE)
#   3. the bound followed pane's cwd, its toplevel followed_pane
#      (@aitask_shadow_target via aitask_shadow_capture.sh)
#   4. this process's own repository toplevel     shadow_cwd  (a stated limit)
#
# Output: see lib/shadow_scope.py. Every resolution outcome exits 0; a
# malformed task id or bad usage exits 2.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

show_help() {
    sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# Echo the toplevel of a directory, or nothing when it is not in a repository.
toplevel_of() {
    git -C "$1" rev-parse --show-toplevel 2>/dev/null || true
}

# The bound followed pane's current directory, or nothing. Reuses the capture
# helper's binding check (sourcing it runs no capture), so a pane on another
# tmux server or an unbound pane yields nothing rather than a guess.
followed_pane_cwd() {
    local state pane
    # shellcheck source=aitask_shadow_capture.sh
    source "$SCRIPT_DIR/aitask_shadow_capture.sh"
    state="$(shadow_self_target 2>/dev/null || true)"
    [[ "$state" == bound:* ]] || return 0
    pane="${state#bound:}"
    ait_tmux display-message -p -t "$pane" '#{pane_current_path}' 2>/dev/null || true
}

main() {
    local task_id="" checkout="" source=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help) show_help; exit 0 ;;
            --checkout)
                [[ $# -ge 2 ]] || { echo "aitask_shadow_scope.sh: --checkout needs a value" >&2; exit 2; }
                checkout="$2"; source="explicit"; shift 2 ;;
            -*) echo "aitask_shadow_scope.sh: unknown option: $1" >&2; exit 2 ;;
            *)
                [[ -z "$task_id" ]] || { echo "aitask_shadow_scope.sh: one task id only" >&2; exit 2; }
                task_id="$1"; shift ;;
        esac
    done
    [[ -n "$task_id" ]] || { show_help >&2; exit 2; }
    if [[ ! "$task_id" =~ ^t?[0-9]+(_[0-9]+)?$ ]]; then
        echo "aitask_shadow_scope.sh: malformed task id: $task_id" >&2
        exit 2
    fi

    if [[ -z "$checkout" ]]; then
        local task_file="" task_name="" wt_out="" wt_state="" wt_path=""
        task_file="$("$SCRIPT_DIR/aitask_shadow_context.sh" "$task_id" 2>/dev/null \
            | sed -n 's/^TASK_FILE://p' | head -n1 || true)"
        if [[ -n "$task_file" && "$task_file" != "NOT_FOUND" ]]; then
            task_name="$(basename "$task_file" .md)"
            wt_out="$("$SCRIPT_DIR/aitask_task_worktree.sh" resolve "$task_name" 2>/dev/null || true)"
            read -r wt_state wt_path <<<"$wt_out" || true
            if [[ "$wt_state" == "USABLE" && -d "$wt_path" ]]; then
                checkout="$wt_path"; source="worktree_record"
            fi
        fi
    fi
    if [[ -z "$checkout" ]]; then
        local pane_dir top
        pane_dir="$(followed_pane_cwd)"
        if [[ -n "$pane_dir" && -d "$pane_dir" ]]; then
            top="$(toplevel_of "$pane_dir")"
            if [[ -n "$top" ]]; then
                checkout="$top"; source="followed_pane"
            fi
        fi
    fi
    if [[ -z "$checkout" ]]; then
        checkout="$(toplevel_of .)"
        [[ -n "$checkout" ]] || checkout="$PWD"
        source="shadow_cwd"
    fi

    local python
    python="$(require_ait_python)"
    exec "$python" "$SCRIPT_DIR/lib/shadow_scope.py" "$task_id" \
        --checkout "$checkout" --checkout-source "$source"
}

main "$@"
