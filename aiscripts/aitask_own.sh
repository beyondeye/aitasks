#!/usr/bin/env bash
# aitask_own.sh - Claim ownership of a task (sync, lock, update status, commit, push)
#
# Consolidates Step 4 of the task-workflow skill into a single script call.
# The calling LLM handles email selection interactively, then passes the
# chosen email here for lock acquisition, metadata update, and git operations.
#
# Also supports a sync-only mode (--sync) for pre-task-selection sync,
# replacing the manual git pull + lock cleanup commands in calling skills.
#
# Usage:
#   ./aiscripts/aitask_own.sh <task_id> [--email <email>]   # Full ownership
#   ./aiscripts/aitask_own.sh --sync                         # Sync-only mode
#
# Output format (structured lines for LLM parsing):
#   OWNED:<task_id>          Task successfully claimed
#   LOCK_FAILED:<owner>      Lock held by another user (exit 1)
#   LOCK_INFRA_MISSING       Lock infrastructure not initialized (exit 1)
#   SYNCED                   Sync-only mode completed
#
# Called by:
#   .claude/skills/task-workflow/SKILL.md (Step 4)
#   .claude/skills/aitask-pick/SKILL.md (Step 0c sync)
#   .claude/skills/aitask-explore/SKILL.md (sync)
#   .claude/skills/aitask-fold/SKILL.md (sync)
#   .claude/skills/aitask-review/SKILL.md (sync)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Configuration ---
TASK_ID=""
EMAIL=""
SYNC_ONLY=false
EMAILS_FILE="aitasks/metadata/emails.txt"

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_own.sh [options] <task_id>
       aitask_own.sh --sync

Claim ownership of a task: sync remote, acquire lock, set status to
Implementing, commit and push. In sync-only mode, just pull and clean
up stale locks.

Arguments:
  task_id         Task number: 166 or t166 (parent), 16_2 or t16_2 (child)
                  Not required in --sync mode.

Options:
  --email EMAIL   Email of the person claiming the task. If provided and new,
                  it is stored to aitasks/metadata/emails.txt (deduplicated).
  --sync          Sync-only mode: git pull + stale lock cleanup, then exit.
                  No task_id required.
  --help, -h      Show this help

Output format (one structured line to stdout):
  OWNED:<task_id>          Task successfully claimed
  LOCK_FAILED:<owner>      Lock held by another user (exit 1)
  LOCK_INFRA_MISSING       Lock infrastructure not initialized (exit 1)
  SYNCED                   Sync-only mode completed

Full ownership mode performs these steps in order:
  1. git pull --ff-only (best-effort sync with remote)
  2. Stale lock cleanup (best-effort)
  3. Store email to emails.txt if provided (deduplicated)
  4. Acquire atomic lock via aitask_lock.sh
  5. Update task status to Implementing via aitask_update.sh
  6. git add + commit + push (push is best-effort)

Examples:
  ./aiscripts/aitask_own.sh 166 --email "user@example.com"
  ./aiscripts/aitask_own.sh t16_2 --email "user@example.com"
  ./aiscripts/aitask_own.sh 166          # No email (skip lock)
  ./aiscripts/aitask_own.sh --sync       # Sync-only mode
EOF
}

# --- Argument Parsing ---
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --email)
                EMAIL="${2:?Missing email address after --email}"
                shift 2
                ;;
            --sync)
                SYNC_ONLY=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            -*)
                die "Unknown option: $1. Use --help for usage."
                ;;
            *)
                if [[ "$1" =~ ^t?[0-9]+(_[0-9]+)?$ ]]; then
                    TASK_ID="${1#t}"
                    shift
                else
                    die "Invalid task ID: $1 (expected format: 166, t166, 16_2, or t16_2)"
                fi
                ;;
        esac
    done

    if [[ "$SYNC_ONLY" == false && -z "$TASK_ID" ]]; then
        die "Task ID is required (or use --sync for sync-only mode). Use --help for usage."
    fi
}

# --- Sync with remote (best-effort) ---
sync_remote() {
    git pull --ff-only --quiet 2>/dev/null || true
    "$SCRIPT_DIR/aitask_lock.sh" --cleanup 2>/dev/null || true
}

# --- Store email (idempotent, deduplicated) ---
store_email() {
    local email="$1"
    if [[ -z "$email" ]]; then
        return
    fi
    local dir
    dir=$(dirname "$EMAILS_FILE")
    mkdir -p "$dir"
    touch "$EMAILS_FILE"
    echo "$email" >> "$EMAILS_FILE"
    sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
}

# --- Acquire lock ---
# Returns: 0=success, 1=lock held by other (LOCK_FAILED printed), 2=infra missing (LOCK_INFRA_MISSING printed)
acquire_lock() {
    local task_id="$1"
    local email="$2"

    if [[ -z "$email" ]]; then
        # No email = no locking possible (user chose to skip)
        return 0
    fi

    local lock_output lock_exit=0
    lock_output=$("$SCRIPT_DIR/aitask_lock.sh" --lock "$task_id" --email "$email" 2>&1) || lock_exit=$?

    if [[ $lock_exit -eq 0 ]]; then
        return 0
    fi

    # Distinguish "already locked by another user" from infrastructure failure
    if echo "$lock_output" | grep -q "already locked by"; then
        local owner
        owner=$(echo "$lock_output" | grep -o 'already locked by [^ ]*' | sed 's/already locked by //')
        [[ -z "$owner" ]] && owner="unknown"
        echo "LOCK_FAILED:$owner"
        return 1
    fi

    # All other failures are infrastructure issues
    echo "LOCK_INFRA_MISSING"
    return 2
}

# --- Update task status ---
update_task_status() {
    local task_id="$1"
    local email="$2"

    if [[ -n "$email" ]]; then
        "$SCRIPT_DIR/aitask_update.sh" --batch "$task_id" --status Implementing --assigned-to "$email"
    else
        "$SCRIPT_DIR/aitask_update.sh" --batch "$task_id" --status Implementing
    fi
}

# --- Commit and push ---
commit_and_push() {
    local task_id="$1"

    git add aitasks/

    # Only commit if there are staged changes (idempotent re-run safety)
    if git diff --cached --quiet; then
        info "No changes to commit (task may already be in Implementing status)"
    else
        git commit -m "ait: Start work on t${task_id}: set status to Implementing" --quiet
    fi

    # Push is best-effort — network failure should not block the workflow
    if ! git push --quiet 2>/dev/null; then
        warn "git push failed (network issue?). Changes committed locally. Push manually later."
    fi
}

# --- Main ---
main() {
    parse_args "$@"

    # Step 1: Sync with remote (both modes)
    sync_remote

    # Sync-only mode: done
    if [[ "$SYNC_ONLY" == true ]]; then
        echo "SYNCED"
        return 0
    fi

    # Step 2: Store email if provided
    if [[ -n "$EMAIL" ]]; then
        store_email "$EMAIL"
    fi

    # Step 3: Acquire lock
    local lock_result=0
    acquire_lock "$TASK_ID" "$EMAIL" || lock_result=$?

    if [[ $lock_result -eq 1 ]]; then
        # LOCK_FAILED already printed by acquire_lock
        exit 1
    fi
    if [[ $lock_result -eq 2 ]]; then
        # LOCK_INFRA_MISSING already printed by acquire_lock
        die "Run 'ait setup' to initialize lock infrastructure."
    fi

    # Step 4: Update task metadata
    update_task_status "$TASK_ID" "$EMAIL"

    # Step 5: Commit and push
    commit_and_push "$TASK_ID"

    # Output success
    echo "OWNED:$TASK_ID"
}

main "$@"
