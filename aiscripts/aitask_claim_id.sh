#!/usr/bin/env bash
# aitask_claim_id.sh - Internal script for atomic task ID management
# Uses a separate git branch 'aitask-ids' with a single file 'next_id.txt'
# as a shared counter. Atomicity is achieved via git push rejection on
# non-fast-forward updates (compare-and-swap semantics).
#
# Usage (internal - not exposed via ait dispatcher):
#   aitask_claim_id.sh --init     Initialize the aitask-ids counter branch
#   aitask_claim_id.sh --claim    Claim the next task ID (default)
#   aitask_claim_id.sh --peek     Show current counter value without claiming
#
# Called by:
#   aitask_create.sh (during finalization)
#   aitask_setup.sh  (during setup)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

BRANCH="aitask-ids"
COUNTER_FILE="next_id.txt"
MAX_RETRIES=5
ID_BUFFER=10

TASK_DIR="${TASK_DIR:-aitasks}"
ARCHIVED_DIR="${ARCHIVED_DIR:-aitasks/archived}"
ARCHIVE_FILE="${ARCHIVE_FILE:-aitasks/archived/old.tar.gz}"

# --- Helpers ---

# Scan all task locations for the maximum existing task number
scan_max_task_id() {
    local max_num=0
    local num

    # Active tasks
    if ls "$TASK_DIR"/t*_*.md &>/dev/null; then
        for f in "$TASK_DIR"/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Archived tasks
    if ls "$ARCHIVED_DIR"/t*_*.md &>/dev/null; then
        for f in "$ARCHIVED_DIR"/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Compressed archive
    if [[ -f "$ARCHIVE_FILE" ]]; then
        while IFS= read -r line; do
            num=$(echo "$line" | grep -oE 't[0-9]+' | head -1 | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done < <(tar -tzf "$ARCHIVE_FILE" 2>/dev/null | grep -E 't[0-9]+')
    fi

    echo "$max_num"
}

# Check that a git remote named 'origin' exists
require_remote() {
    if ! git remote get-url origin &>/dev/null; then
        die "No git remote 'origin' configured. Cannot use atomic task ID counter."
    fi
}

# --- Init: create the aitask-ids branch ---

init_counter_branch() {
    require_remote

    # Check if branch already exists on remote
    if git ls-remote --heads origin "$BRANCH" 2>/dev/null | grep -q "$BRANCH"; then
        info "Counter branch '$BRANCH' already exists on remote."
        git fetch origin "$BRANCH" --quiet 2>/dev/null || true
        local current_val
        current_val=$(git show "origin/$BRANCH:$COUNTER_FILE" 2>/dev/null || echo "?")
        info "Current counter value: $current_val"
        return 0
    fi

    # Scan for max existing task ID
    local max_id
    max_id=$(scan_max_task_id)
    local next_id=$((max_id + ID_BUFFER))

    info "Max existing task ID: t$max_id"
    info "Initializing counter branch with next_id=$next_id (max + $ID_BUFFER buffer)"

    # Create the branch using git plumbing (no checkout needed)
    local blob_hash tree_hash commit_hash

    blob_hash=$(echo "$next_id" | git hash-object -w --stdin)
    tree_hash=$(printf "100644 blob %s\t%s\n" "$blob_hash" "$COUNTER_FILE" | git mktree)
    commit_hash=$(echo "Initialize task ID counter at $next_id" | git commit-tree "$tree_hash")

    # Push as new branch
    if git push origin "$commit_hash:refs/heads/$BRANCH" 2>/dev/null; then
        success "Counter branch '$BRANCH' created with next_id=$next_id"
    else
        die "Failed to push counter branch. Check remote permissions."
    fi
}

# --- Claim: atomically get the next task ID ---

claim_next_id() {
    require_remote

    local attempt=0

    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))

        # Step 1: Fetch latest counter
        if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
            die "Failed to fetch '$BRANCH' from origin. Run 'ait setup' to initialize the counter."
        fi

        # Step 2: Read current value
        local current_id
        current_id=$(git show "origin/$BRANCH:$COUNTER_FILE" 2>/dev/null) || {
            die "Could not read $COUNTER_FILE from origin/$BRANCH. Branch may be corrupted."
        }

        # Trim whitespace
        current_id=$(echo "$current_id" | tr -d '[:space:]')

        # Validate it's a number
        if ! [[ "$current_id" =~ ^[0-9]+$ ]]; then
            die "Invalid counter value: '$current_id' (expected a number)"
        fi

        # Step 3: Compute new value
        local new_id=$((current_id + 1))

        # Step 4: Create new commit via git plumbing
        local blob_hash tree_hash commit_hash parent_hash

        parent_hash=$(git rev-parse "origin/$BRANCH")
        blob_hash=$(echo "$new_id" | git hash-object -w --stdin)
        tree_hash=$(printf "100644 blob %s\t%s\n" "$blob_hash" "$COUNTER_FILE" | git mktree)
        commit_hash=$(echo "Claim task ID t$current_id, advance counter to $new_id" | \
            git commit-tree "$tree_hash" -p "$parent_hash")

        # Step 5: Push - fails if another PC claimed simultaneously (non-fast-forward)
        if git push origin "$commit_hash:refs/heads/$BRANCH" 2>/dev/null; then
            echo "$current_id"
            return 0
        fi

        # Push failed (race condition) - retry
        if [[ $attempt -lt $MAX_RETRIES ]]; then
            warn "ID claim race detected (attempt $attempt/$MAX_RETRIES), retrying..." >&2
            sleep "0.$((RANDOM % 4 + 1))"
        fi
    done

    die "Failed to claim task ID after $MAX_RETRIES attempts. Try again later."
}

# --- Peek: show current counter without claiming ---

peek_counter() {
    require_remote

    if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
        die "Failed to fetch '$BRANCH'. Run 'ait setup' to initialize."
    fi

    local current_id
    current_id=$(git show "origin/$BRANCH:$COUNTER_FILE" 2>/dev/null) || {
        die "Could not read counter."
    }
    echo "$current_id"
}

# --- Main ---

show_help() {
    cat <<'EOF'
Usage: aitask_claim_id.sh [--init|--claim|--peek]

Internal script for atomic task ID management.

Options:
  --init    Initialize the aitask-ids counter branch on remote
  --claim   Claim the next task ID atomically (default)
  --peek    Show current counter value without claiming
  --help    Show this help message
EOF
}

case "${1:-claim}" in
    --init|init)
        init_counter_branch
        ;;
    --claim|claim)
        claim_next_id
        ;;
    --peek|peek)
        peek_counter
        ;;
    --help|-h)
        show_help
        ;;
    *)
        die "Unknown option: $1. Use --help for usage."
        ;;
esac
