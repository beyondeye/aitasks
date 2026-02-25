#!/usr/bin/env bash
# aitask_lock.sh - Atomic task lock management
# Uses a separate git orphan branch 'aitask-locks' with per-task lock files.
# Atomicity is achieved via git push rejection on non-fast-forward updates
# (compare-and-swap semantics).
#
# Public usage (via ait dispatcher):
#   ait lock <task_id>                     Lock task (auto-detects email)
#   ait lock <task_id> --email <email>     Lock task with explicit email
#   ait lock --unlock <task_id>            Release lock
#   ait lock --check <task_id>             Check if locked (exit 0=locked, 1=free)
#   ait lock --list                        List all active locks
#   ait lock --init                        Initialize the aitask-locks branch
#   ait lock --cleanup                     Remove stale locks for archived tasks
#
# Also called internally by:
#   aiscripts/aitask_pick_own.sh (lock acquisition and cleanup)
#   .claude/skills/aitask-pick/SKILL.md (during task pick workflow)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

BRANCH="aitask-locks"
MAX_RETRIES=5

DEBUG=false

TASK_DIR="${TASK_DIR:-aitasks}"
ARCHIVED_DIR="${ARCHIVED_DIR:-aitasks/archived}"

# --- Helpers ---

debug() {
    if [[ "$DEBUG" == true ]]; then
        info "[debug] $*" >&2
    fi
}

# Check that a git remote named 'origin' exists
require_remote() {
    if ! git remote get-url origin &>/dev/null; then
        die_code 10 "No git remote 'origin' configured. Cannot use atomic task locks."
    fi
}

get_hostname() {
    hostname 2>/dev/null || echo "unknown"
}

get_timestamp() {
    date '+%Y-%m-%d %H:%M'
}

# --- Init: create the aitask-locks branch ---

init_lock_branch() {
    require_remote

    # Check if branch already exists on remote
    if git ls-remote --heads origin "$BRANCH" 2>/dev/null | grep -q "$BRANCH"; then
        info "Lock branch '$BRANCH' already exists on remote."
        return 0
    fi

    info "Initializing lock branch '$BRANCH'..."

    # Create an empty tree and initial commit via git plumbing
    local empty_tree_hash commit_hash
    empty_tree_hash=$(printf '' | git mktree)
    commit_hash=$(echo "ait: Initialize task lock branch" | git commit-tree "$empty_tree_hash")

    # Push as new branch
    if git push origin "$commit_hash:refs/heads/$BRANCH" 2>/dev/null; then
        success "Lock branch '$BRANCH' created"
    else
        die "Failed to push lock branch. Check remote permissions."
    fi
}

# --- Lock: atomically acquire a task lock ---

lock_task() {
    local task_id="$1"
    local email="$2"
    local lock_file="t${task_id}_lock.yaml"

    require_remote
    debug "Attempting to lock task t$task_id for $email"

    local attempt=0

    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))
        debug "Attempt $attempt/$MAX_RETRIES"

        # Step 1: Fetch latest lock branch
        debug "Fetching branch '$BRANCH' from origin..."
        if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
            die_code 11 "Failed to fetch '$BRANCH' from origin. Run 'ait setup' to initialize."
        fi
        debug "Fetch successful"

        local parent_hash current_tree_hash
        parent_hash=$(git rev-parse "origin/$BRANCH")
        current_tree_hash=$(git rev-parse "origin/$BRANCH^{tree}")

        # Step 2: Check if lock file already exists in tree
        if git ls-tree "$current_tree_hash" -- "$lock_file" 2>/dev/null | grep -q "$lock_file"; then
            # Lock exists — read it for informative message
            local lock_content locked_by locked_at
            lock_content=$(git show "origin/$BRANCH:$lock_file" 2>/dev/null || echo "unknown")
            locked_by=$(echo "$lock_content" | grep '^locked_by:' | sed 's/locked_by: *//')
            locked_at=$(echo "$lock_content" | grep '^locked_at:' | sed 's/locked_at: *//')

            # Idempotent: if same email owns the lock, refresh it
            if [[ "$locked_by" == "$email" ]]; then
                debug "Lock already held by same user, refreshing"
            else
                die "Task t$task_id is already locked by $locked_by (since $locked_at)"
            fi
        fi

        # Step 3: Build lock file content (YAML)
        local lock_yaml
        lock_yaml="task_id: $task_id
locked_by: $email
locked_at: $(get_timestamp)
hostname: $(get_hostname)"

        # Step 4: Create new commit via git plumbing
        local blob_hash new_tree_hash commit_hash_new

        blob_hash=$(echo "$lock_yaml" | git hash-object -w --stdin)

        # Build new tree: existing entries (minus old lock if refreshing) + new lock
        new_tree_hash=$( {
            git ls-tree "$current_tree_hash" | grep -v "	${lock_file}$" || true
            printf "100644 blob %s\t%s\n" "$blob_hash" "$lock_file"
        } | git mktree )

        commit_hash_new=$(echo "ait: Lock task t$task_id for $email" | \
            git commit-tree "$new_tree_hash" -p "$parent_hash")

        # Step 5: Push — fails if another PC locked simultaneously
        debug "Pushing to origin..."
        if git push origin "$commit_hash_new:refs/heads/$BRANCH" 2>/dev/null; then
            debug "Lock acquired for t$task_id"
            success "Locked task t$task_id"
            return 0
        fi

        # Push failed (race condition) — retry
        debug "Push failed (race condition)"
        if [[ $attempt -lt $MAX_RETRIES ]]; then
            warn "Lock race detected (attempt $attempt/$MAX_RETRIES), retrying..." >&2
            sleep "0.$((RANDOM % 4 + 1))"
        fi
    done

    die_code 12 "Failed to lock task t$task_id after $MAX_RETRIES attempts."
}

# --- Unlock: atomically release a task lock ---

unlock_task() {
    local task_id="$1"
    local lock_file="t${task_id}_lock.yaml"

    require_remote
    debug "Attempting to unlock task t$task_id"

    local attempt=0

    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))
        debug "Attempt $attempt/$MAX_RETRIES"

        # Step 1: Fetch latest
        if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
            die_code 11 "Failed to fetch '$BRANCH'. Run 'ait setup' to initialize."
        fi

        local parent_hash current_tree_hash
        parent_hash=$(git rev-parse "origin/$BRANCH")
        current_tree_hash=$(git rev-parse "origin/$BRANCH^{tree}")

        # Step 2: If lock file doesn't exist, succeed silently (idempotent)
        if ! git ls-tree "$current_tree_hash" -- "$lock_file" 2>/dev/null | grep -q "$lock_file"; then
            debug "Lock file does not exist, nothing to unlock"
            return 0
        fi

        # Step 3: Build new tree WITHOUT the lock file
        local new_tree_hash commit_hash_new
        new_tree_hash=$( { git ls-tree "$current_tree_hash" | grep -v "	${lock_file}$" || true; } | git mktree )
        commit_hash_new=$(echo "ait: Unlock task t$task_id" | \
            git commit-tree "$new_tree_hash" -p "$parent_hash")

        # Step 4: Push
        debug "Pushing to origin..."
        if git push origin "$commit_hash_new:refs/heads/$BRANCH" 2>/dev/null; then
            debug "Lock released for t$task_id"
            return 0
        fi

        # Retry on race
        debug "Push failed (race condition)"
        if [[ $attempt -lt $MAX_RETRIES ]]; then
            warn "Unlock race detected (attempt $attempt/$MAX_RETRIES), retrying..." >&2
            sleep "0.$((RANDOM % 4 + 1))"
        fi
    done

    die_code 12 "Failed to unlock task t$task_id after $MAX_RETRIES attempts."
}

# --- Check: is a task locked? ---

check_lock() {
    local task_id="$1"
    local lock_file="t${task_id}_lock.yaml"

    require_remote

    if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
        # Branch doesn't exist — not locked
        return 1
    fi

    local current_tree_hash
    current_tree_hash=$(git rev-parse "origin/$BRANCH^{tree}" 2>/dev/null) || return 1

    if git ls-tree "$current_tree_hash" -- "$lock_file" 2>/dev/null | grep -q "$lock_file"; then
        # Locked — print lock info to stdout
        git show "origin/$BRANCH:$lock_file" 2>/dev/null
        return 0
    else
        return 1
    fi
}

# --- List: show all active locks ---

list_locks() {
    require_remote

    if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
        info "No locks (branch not initialized)"
        return 0
    fi

    local current_tree_hash
    current_tree_hash=$(git rev-parse "origin/$BRANCH^{tree}" 2>/dev/null) || {
        info "No locks"
        return 0
    }

    local lock_files
    lock_files=$(git ls-tree "$current_tree_hash" | grep '_lock\.yaml' | awk '{print $4}')

    if [[ -z "$lock_files" ]]; then
        info "No active locks"
        return 0
    fi

    while IFS= read -r lf; do
        local content tid lby lat lhost
        content=$(git show "origin/$BRANCH:$lf" 2>/dev/null)
        tid=$(echo "$content" | grep '^task_id:' | sed 's/task_id: *//')
        lby=$(echo "$content" | grep '^locked_by:' | sed 's/locked_by: *//')
        lat=$(echo "$content" | grep '^locked_at:' | sed 's/locked_at: *//')
        lhost=$(echo "$content" | grep '^hostname:' | sed 's/hostname: *//')
        echo "t${tid}: locked by $lby on $lhost since $lat"
    done <<< "$lock_files"
}

# --- Cleanup: remove stale locks for archived tasks ---

cleanup_locks() {
    require_remote

    if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
        debug "Lock branch not found, nothing to clean up"
        return 0
    fi

    local parent_hash current_tree_hash
    parent_hash=$(git rev-parse "origin/$BRANCH")
    current_tree_hash=$(git rev-parse "origin/$BRANCH^{tree}" 2>/dev/null) || return 0

    local lock_files
    lock_files=$(git ls-tree "$current_tree_hash" | grep '_lock\.yaml' | awk '{print $4}')

    [[ -z "$lock_files" ]] && return 0

    local stale_files=()

    while IFS= read -r lf; do
        # Extract task ID from filename (t109_lock.yaml -> 109)
        local tid
        tid=$(echo "$lf" | grep -oE '^t[0-9]+' | sed 's/t//')

        # Check if task is archived
        if ls "$ARCHIVED_DIR"/t${tid}_*.md &>/dev/null; then
            stale_files+=("$lf")
            debug "Stale lock: $lf (task archived)"
        fi
    done <<< "$lock_files"

    if [[ ${#stale_files[@]} -eq 0 ]]; then
        debug "No stale locks found"
        return 0
    fi

    info "Removing ${#stale_files[@]} stale lock(s)..."

    # Build grep pattern to filter out stale lock files
    local filter_pattern
    filter_pattern=$(printf "%s\n" "${stale_files[@]}" | sed 's/\./\\./g' | paste -sd'|' -)

    local attempt=0

    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))

        local new_tree_hash commit_hash_new
        new_tree_hash=$( { git ls-tree "$current_tree_hash" | grep -vE "	(${filter_pattern})$" || true; } | git mktree )
        commit_hash_new=$(echo "ait: Cleanup ${#stale_files[@]} stale lock(s)" | \
            git commit-tree "$new_tree_hash" -p "$parent_hash")

        if git push origin "$commit_hash_new:refs/heads/$BRANCH" 2>/dev/null; then
            success "Cleaned up ${#stale_files[@]} stale lock(s)"
            return 0
        fi

        # Re-fetch and rebuild on retry (tree may have changed)
        debug "Push failed during cleanup, retrying..."
        sleep "0.$((RANDOM % 4 + 1))"
        git fetch origin "$BRANCH" --quiet 2>/dev/null || break
        parent_hash=$(git rev-parse "origin/$BRANCH")
        current_tree_hash=$(git rev-parse "origin/$BRANCH^{tree}")
    done

    warn "Failed to push stale lock cleanup after $MAX_RETRIES attempts"
}

# --- Email auto-detection ---

# Auto-detect user email: userconfig.yaml -> emails.txt
# Mirrors the board TUI's _get_user_email() logic
get_user_email_with_fallback() {
    local email
    email=$(get_user_email)
    if [[ -n "$email" ]]; then
        echo "$email"
        return
    fi
    local emails_file="${TASK_DIR:-aitasks}/metadata/emails.txt"
    if [[ -f "$emails_file" ]]; then
        head -1 "$emails_file" | tr -d '[:space:]'
    fi
}

# Resolve email for --lock: use explicit arg or auto-detect
# Usage: resolve_lock_email [--email <email>]
# Remaining args after resolution are left in LOCK_EXTRA_ARGS
resolve_lock_email() {
    if [[ "${1:-}" == "--email" ]]; then
        echo "${2:?Missing email address after --email}"
        return
    fi
    local email
    email=$(get_user_email_with_fallback)
    if [[ -z "$email" ]]; then
        die "No email provided and none found in userconfig.yaml or emails.txt. Use --email <email> or configure aitasks/metadata/userconfig.yaml"
    fi
    debug "Auto-detected email: $email"
    echo "$email"
}

# --- Main ---

show_help() {
    cat <<'EOF'
Usage: ait lock [--debug] <command> [args]

Atomic task lock management. Prevents two users from working on the same
task simultaneously. Locks are stored on a separate git branch (aitask-locks).

Commands:
  <task_id>                        Lock a task (auto-detects email from userconfig)
  --lock <task_id> [--email EMAIL] Lock a task (explicit syntax)
  --unlock <task_id>               Release a task lock
  --check <task_id>                Check if locked (exit 0=locked, 1=free)
  --list                           List all currently locked tasks
  --init                           Initialize the aitask-locks branch on remote
  --cleanup                        Remove stale locks for archived tasks

Options:
  --email EMAIL  Override email for locking (default: auto-detect from
                 aitasks/metadata/userconfig.yaml or emails.txt)
  --debug        Enable verbose debug output
  --help         Show this help message

Examples:
  ait lock 42                      # Lock task t42 (auto-detect email)
  ait lock 42 --email user@co.com  # Lock with explicit email
  ait lock --unlock 42             # Unlock task t42
  ait lock --check 42              # Check if t42 is locked
  ait lock --list                  # Show all locks
EOF
}

# Parse --debug flag first
while [[ "${1:-}" == "--debug" ]]; do
    DEBUG=true
    shift
done

case "${1:-}" in
    --init|init)
        init_lock_branch
        ;;
    --lock|lock)
        shift
        LOCK_TASK_ID="${1:?Usage: ait lock <task_id> [--email <email>]}"
        shift
        LOCK_EMAIL=$(resolve_lock_email "$@")
        lock_task "$LOCK_TASK_ID" "$LOCK_EMAIL"
        ;;
    --unlock|unlock)
        shift
        UNLOCK_TASK_ID="${1:?Usage: aitask_lock.sh --unlock <task_id>}"
        unlock_task "$UNLOCK_TASK_ID"
        ;;
    --check|check)
        shift
        CHECK_TASK_ID="${1:?Usage: aitask_lock.sh --check <task_id>}"
        check_lock "$CHECK_TASK_ID"
        ;;
    --list|list)
        list_locks
        ;;
    --cleanup|cleanup)
        cleanup_locks
        ;;
    --help|-h)
        show_help
        ;;
    "")
        die "No command specified. Use --help for usage."
        ;;
    *)
        # Bare task ID: treat as --lock shortcut (e.g., "ait lock 42")
        if [[ "$1" =~ ^t?[0-9]+(_[0-9]+)?$ ]]; then
            LOCK_TASK_ID="${1#t}"
            shift
            LOCK_EMAIL=$(resolve_lock_email "$@")
            lock_task "$LOCK_TASK_ID" "$LOCK_EMAIL"
        else
            die "Unknown option: $1. Use --help for usage."
        fi
        ;;
esac
