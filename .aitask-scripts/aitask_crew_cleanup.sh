#!/usr/bin/env bash
# aitask_crew_cleanup.sh - Remove completed agentcrew worktrees and optionally branches.
#
# Usage:
#   ait crew cleanup --crew <id> [--delete-branch] [--batch]
#   ait crew cleanup --all-completed [--delete-branch] [--batch]
#
# Only cleans crews in terminal state (Completed, Error, Aborted).
# Output (batch):
#   CLEANED:<id>          — Worktree removed successfully
#   NOT_TERMINAL:<id>:<s> — Crew is not in a terminal state
#   NOT_FOUND:<id>        — Crew worktree not found

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/agentcrew_utils.sh
source "$SCRIPT_DIR/lib/agentcrew_utils.sh"

# --- Argument parsing ---
CREW_ID=""
ALL_COMPLETED=false
DELETE_BRANCH=false
BATCH=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --crew)
            CREW_ID="$2"
            shift 2
            ;;
        --all-completed)
            ALL_COMPLETED=true
            shift
            ;;
        --delete-branch)
            DELETE_BRANCH=true
            shift
            ;;
        --batch)
            BATCH=true
            shift
            ;;
        --help|-h)
            echo "Usage: ait crew cleanup --crew <id> [--delete-branch] [--batch]"
            echo "       ait crew cleanup --all-completed [--delete-branch] [--batch]"
            echo ""
            echo "Remove completed agentcrew worktrees and optionally delete branches."
            echo "Only crews in terminal state (Completed, Error, Aborted) are cleaned."
            exit 0
            ;;
        *)
            die "Unknown argument: $1"
            ;;
    esac
done

if [[ -z "$CREW_ID" ]] && ! $ALL_COMPLETED; then
    die "Either --crew <id> or --all-completed is required. Run 'ait crew cleanup --help' for usage."
fi

# Terminal states that allow cleanup
is_terminal_state() {
    local status="$1"
    case "$status" in
        "$CREW_STATUS_COMPLETED"|"$AGENT_STATUS_ERROR"|"$AGENT_STATUS_ABORTED")
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Clean a single crew
cleanup_crew() {
    local cid="$1"
    local wt_path
    wt_path="$(agentcrew_worktree_path "$cid")"

    if [[ ! -d "$wt_path" ]]; then
        if $BATCH; then
            echo "NOT_FOUND:$cid"
        else
            warn "Crew '$cid' not found: worktree '$wt_path' does not exist"
        fi
        return 1
    fi

    # Read crew status
    local status_file="$wt_path/_crew_status.yaml"
    local crew_status=""
    if [[ -f "$status_file" ]]; then
        crew_status=$(read_yaml_field "$status_file" "status")
    fi

    if ! is_terminal_state "$crew_status"; then
        if $BATCH; then
            echo "NOT_TERMINAL:$cid:$crew_status"
        else
            warn "Crew '$cid' has status '$crew_status' — only terminal states (Completed, Error, Aborted) can be cleaned"
        fi
        return 1
    fi

    # Remove worktree
    git worktree remove "$wt_path" --force 2>/dev/null || {
        # Fallback: manual removal if git worktree remove fails
        rm -rf "$wt_path"
    }

    # Optionally delete the branch
    local branch_name
    branch_name="$(crew_branch_name "$cid")"
    if $DELETE_BRANCH; then
        git branch -D "$branch_name" 2>/dev/null || true
    fi

    # Prune stale worktree references
    git worktree prune 2>/dev/null || true

    if $BATCH; then
        echo "CLEANED:$cid"
    else
        info "Cleaned crew '$cid'"
        if $DELETE_BRANCH; then
            info "Deleted branch '$branch_name'"
        fi
    fi
    return 0
}

# --- Main ---
if $ALL_COMPLETED; then
    if [[ ! -d "$AGENTCREW_DIR" ]]; then
        if $BATCH; then
            echo "NO_CREWS"
        else
            info "No agentcrews directory found."
        fi
        exit 0
    fi

    cleaned=0
    for entry in "$AGENTCREW_DIR"/crew-*; do
        [[ -d "$entry" ]] || continue
        cid="${entry##*/crew-}"
        if cleanup_crew "$cid"; then
            cleaned=$((cleaned + 1))
        fi
    done

    if ! $BATCH; then
        info "Cleaned $cleaned crew(s)"
    fi
else
    validate_crew_id "$CREW_ID"
    cleanup_crew "$CREW_ID"
fi
