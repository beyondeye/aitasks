#!/usr/bin/env bash
# aitask_brainstorm_delete.sh - Completely delete a brainstorm session.
#
# Usage: ait brainstorm delete <task_num> [--yes]
#
# Removes the brainstorm session files and crew worktree entirely.
# Prompts for confirmation unless --yes is passed.
#
# Output:
#   DELETED:<task_num>      Session deleted

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

PYTHON="$(require_ait_python)"

# --- Usage ---
show_help() {
    cat <<'HELP'
Usage: ait brainstorm delete <task_num> [--yes]

Completely delete a brainstorm session, removing all session files
and the crew worktree.

Arguments:
  <task_num>    Task number (required)

Options:
  --yes         Skip confirmation prompt

Output:
  DELETED:<task_num>      Session deleted

Example:
  ait brainstorm delete 42
  ait brainstorm delete 42 --yes
HELP
}

# --- Argument parsing ---
TASK_NUM=""
SKIP_CONFIRM=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            show_help; exit 0 ;;
        --yes|-y)
            SKIP_CONFIRM=true; shift ;;
        -*)
            die "Unknown option: $1. Run 'ait brainstorm delete --help' for usage." ;;
        *)
            if [[ -z "$TASK_NUM" ]]; then
                TASK_NUM="$1"; shift
            else
                die "Unexpected argument: $1"
            fi
            ;;
    esac
done

[[ -z "$TASK_NUM" ]] && die "Missing required <task_num>. Run 'ait brainstorm delete --help' for usage."

# --- Verify session exists ---
exists_output=$("$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" exists --task-num "$TASK_NUM" 2>&1) || {
    die "Failed to check session: $exists_output"
}

if [[ "$exists_output" == "NOT_EXISTS" ]]; then
    die "No brainstorm session found for task $TASK_NUM"
fi

# --- Confirmation ---
if ! $SKIP_CONFIRM; then
    warn "This will permanently delete the brainstorm session for task $TASK_NUM."
    printf "Are you sure? [y/N] "
    read -r response
    case "$response" in
        [yY]|[yY][eE][sS]) ;;
        *) info "Aborted."; exit 0 ;;
    esac
fi

# --- Delete session files via Python CLI ---
delete_output=$("$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" delete --task-num "$TASK_NUM" 2>&1) || {
    die "Failed to delete session: $delete_output"
}

# --- Clean up crew worktree and branch (if still present) ---
CREW_ID="brainstorm-${TASK_NUM}"
cleanup_output=$(bash "$SCRIPT_DIR/aitask_crew_cleanup.sh" --crew "$CREW_ID" --delete-branch --batch 2>&1) || {
    # Session files already deleted by Python; crew cleanup may fail if worktree is gone
    case "$cleanup_output" in
        NOT_FOUND:*|NOT_TERMINAL:*)
            # Prune first — a stale worktree registration in .git/worktrees/
            # would otherwise pin "crew-${CREW_ID}" as "checked out elsewhere"
            # and `git branch -D` would refuse.
            git worktree prune 2>/dev/null || true
            if git show-ref --verify --quiet "refs/heads/crew-${CREW_ID}"; then
                if git branch -D "crew-${CREW_ID}" >/dev/null 2>&1; then
                    info "Cleaned: stale crew-${CREW_ID} branch removed"
                else
                    warn "Failed to delete stale branch crew-${CREW_ID}"
                fi
            fi
            # Best-effort remote cleanup — silent on failure (no remote, no
            # perms, branch never pushed, etc. are all acceptable).
            git push origin --delete "crew-${CREW_ID}" 2>/dev/null || true
            ;;
        *)
            warn "Crew cleanup note: $cleanup_output"
            ;;
    esac
}

success "Brainstorm session deleted for task $TASK_NUM"
echo "DELETED:${TASK_NUM}"
