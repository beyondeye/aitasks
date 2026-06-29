#!/usr/bin/env bash
# aitask_claim_id.sh - Internal script for atomic task ID management
# Uses a separate git branch 'aitask-ids' with a single file 'next_id.txt'
# as a shared counter. Atomicity is achieved via git push rejection on
# non-fast-forward updates (compare-and-swap semantics).
#
# When no git remote is configured, uses a local-only aitask-ids branch
# (auto-created on first claim). When a remote is later added, the local
# branch is automatically pushed to remote on next claim (auto-upgrade).
#
# Usage (internal - not exposed via ait dispatcher):
#   aitask_claim_id.sh --init     Initialize the aitask-ids counter branch
#   aitask_claim_id.sh --claim    Claim the next task ID (default)
#   aitask_claim_id.sh --peek     Show current counter value without claiming
#   aitask_claim_id.sh --resync   Repair the counter against active+archived tasks
#
# Called by:
#   aitask_create.sh (during finalization)
#   aitask_setup.sh  (during setup)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/archive_scan.sh
source "$SCRIPT_DIR/lib/archive_scan.sh"

BRANCH="aitask-ids"
COUNTER_FILE="next_id.txt"
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

# Hot-path scan: active task files only. Do not traverse aitasks/archived or
# inspect archive tarballs during normal ID claims.
scan_max_active_task_id() {
    local task_dir="$1"
    local max_num=0
    local num

    if ls "$task_dir"/t*_*.md &>/dev/null; then
        for f in "$task_dir"/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    if ls "$task_dir"/t*/t*_*.md &>/dev/null; then
        for f in "$task_dir"/t*/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    echo "$max_num"
}

safe_claim_id_from_counter() {
    local current_id="$1"
    local active_max active_next
    active_max=$(scan_max_active_task_id "$TASK_DIR")
    active_next=$((active_max + 1))
    if [[ "$current_id" -lt "$active_next" ]]; then
        debug "Counter drift detected on active tasks: counter=$current_id active_next=$active_next"
        echo "$active_next"
    else
        echo "$current_id"
    fi
}

full_repair_next_id() {
    local max_id
    max_id=$(scan_max_task_id "$TASK_DIR" "$ARCHIVED_DIR")
    echo $((max_id + 1))
}

commit_counter_value() {
    local ref_name="$1"
    local parent_ref="$2"
    local next_id="$3"
    local message="$4"
    local blob_hash tree_hash commit_hash parent_hash

    parent_hash=$(git rev-parse "$parent_ref")
    blob_hash=$(echo "$next_id" | git hash-object -w --stdin)
    tree_hash=$(printf "100644 blob %s\t%s\n" "$blob_hash" "$COUNTER_FILE" | git mktree)
    commit_hash=$(echo "$message" | git commit-tree "$tree_hash" -p "$parent_hash")
    git update-ref "$ref_name" "$commit_hash"
    echo "$commit_hash"
}

# Check whether a git remote named 'origin' exists (non-fatal)
has_remote() {
    git remote get-url origin &>/dev/null
}

# Check that a git remote named 'origin' exists (fatal)
require_remote() {
    if ! has_remote; then
        die "No git remote 'origin' configured. Cannot initialize atomic task ID counter."
    fi
}

# Query origin for the counter branch WITHOUT writing .git/FETCH_HEAD.
# Echoes exactly one of:
#   PRESENT         - branch exists on origin
#   ABSENT          - origin reachable, branch not present
#   ERROR:<message> - could not query origin (network/auth/etc.)
# This disambiguates a failed `git fetch`: ls-remote does not touch FETCH_HEAD,
# so it still reports PRESENT in the exact scenario where a fetch fails on an
# unwritable FETCH_HEAD — letting the caller surface the real error instead of
# mistaking it for a missing branch and looping the auto-upgrade path.
remote_branch_state() {
    local ls_out
    if ls_out=$(git ls-remote --heads origin "$BRANCH" 2>&1); then
        if printf '%s' "$ls_out" | grep -q "refs/heads/$BRANCH"; then
            echo "PRESENT"
        else
            echo "ABSENT"
        fi
    else
        echo "ERROR:$(printf '%s' "$ls_out" | tr '\n' ' ')"
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
    max_id=$(scan_max_task_id "$TASK_DIR" "$ARCHIVED_DIR")
    local next_id=$((max_id + 1))

    info "Max existing task ID: t$max_id"
    info "Initializing counter branch with next_id=$next_id (max + 1)"

    # Create the branch using git plumbing (no checkout needed)
    local blob_hash tree_hash commit_hash

    blob_hash=$(echo "$next_id" | git hash-object -w --stdin)
    tree_hash=$(printf "100644 blob %s\t%s\n" "$blob_hash" "$COUNTER_FILE" | git mktree)
    commit_hash=$(echo "ait: Initialize task ID counter at $next_id" | git commit-tree "$tree_hash")

    # Push as new branch
    if git push origin "$commit_hash:refs/heads/$BRANCH" 2>/dev/null; then
        success "Counter branch '$BRANCH' created with next_id=$next_id"
    else
        die "Failed to push counter branch. Check remote permissions."
    fi
}

# --- Local branch helpers ---

# Check if local aitask-ids branch exists
has_local_branch() {
    git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null
}

# Auto-initialize a local counter branch (no remote needed)
init_local_branch() {
    local max_id
    max_id=$(scan_max_task_id "$TASK_DIR" "$ARCHIVED_DIR")
    local next_id=$((max_id + 1))

    debug "Initializing local counter branch with next_id=$next_id (max=$max_id + 1)"

    local blob_hash tree_hash commit_hash
    blob_hash=$(echo "$next_id" | git hash-object -w --stdin)
    tree_hash=$(printf "100644 blob %s\t%s\n" "$blob_hash" "$COUNTER_FILE" | git mktree)
    commit_hash=$(echo "ait: Initialize local task ID counter at $next_id" | git commit-tree "$tree_hash")
    git update-ref "refs/heads/$BRANCH" "$commit_hash"

    info "Local counter branch '$BRANCH' created with next_id=$next_id" >&2
}

# Claim next ID from local branch (no remote, no CAS needed)
claim_local() {
    if ! has_local_branch; then
        init_local_branch
    fi

    local current_id
    current_id=$(git show "$BRANCH:$COUNTER_FILE" 2>/dev/null | tr -d '[:space:]') || {
        die "Could not read $COUNTER_FILE from local $BRANCH. Branch may be corrupted."
    }

    if ! [[ "$current_id" =~ ^[0-9]+$ ]]; then
        die "Invalid local counter value: '$current_id' (expected a number)"
    fi

    local claimed_id
    claimed_id=$(safe_claim_id_from_counter "$current_id")
    local new_id=$((claimed_id + 1))
    debug "Local claim: ID $claimed_id, advancing counter from $current_id to $new_id"

    commit_counter_value "refs/heads/$BRANCH" "$BRANCH" "$new_id" \
        "ait: Claim task ID t$claimed_id, advance counter to $new_id" >/dev/null

    echo "$claimed_id"
}

# Try to push local branch to remote (auto-upgrade when remote becomes available)
try_push_local_to_remote() {
    if has_local_branch; then
        debug "Attempting to push local '$BRANCH' to remote (auto-upgrade)..."
        local push_out
        if push_out=$(git push origin "$BRANCH:refs/heads/$BRANCH" 2>&1); then
            # Only announce an auto-upgrade when the push actually created or
            # advanced the remote branch. A no-op "up-to-date" push must not
            # masquerade as an upgrade (that was the misleading-loop symptom).
            if ! printf '%s' "$push_out" | grep -qi "up-to-date"; then
                info "Pushed local counter branch to remote (auto-upgrade)" >&2
            fi
            git fetch origin "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" --quiet 2>/dev/null || true
            return 0
        fi
        debug "Push of local branch failed: $push_out"
    fi
    return 1
}

# --- Claim: atomically get the next task ID ---

claim_next_id() {
    # No remote: use local-only counter branch
    if ! has_remote; then
        debug "No remote — using local counter branch"
        claim_local
        return 0
    fi

    debug "Starting claim (max retries: $MAX_RETRIES)"

    local attempt=0

    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))
        debug "Attempt $attempt/$MAX_RETRIES"

        # Step 1: Fetch latest counter. Capture stderr (do NOT discard it) and
        # use an explicit refspec so origin/$BRANCH is reliably updated across
        # git versions/configs.
        debug "Fetching branch '$BRANCH' from origin..."
        local fetch_err
        if ! fetch_err=$(git fetch origin \
            "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" --quiet 2>&1 >/dev/null); then
            # Fetch failed. Only a genuinely-absent remote branch may trigger
            # the auto-upgrade path (or suggest 'ait setup'). A real fetch /
            # environment error (network, auth, unwritable .git/FETCH_HEAD) must
            # be surfaced verbatim — never mistaken for a missing branch.
            local rstate
            rstate=$(remote_branch_state)
            case "$rstate" in
                PRESENT)
                    die "Failed to fetch counter branch '$BRANCH' from origin: ${fetch_err:-unknown git fetch error}"
                    ;;
                ERROR:*)
                    die "Cannot reach origin to verify counter branch '$BRANCH': ${rstate#ERROR:}"
                    ;;
                *)  # ABSENT — remote branch missing; auto-upgrade from local.
                    if try_push_local_to_remote; then
                        continue  # Retry with the now-available remote branch
                    fi
                    die "Counter branch '$BRANCH' is not initialized on origin and no local branch exists to upgrade. Run 'ait setup' to initialize the counter."
                    ;;
            esac
        fi
        debug "Fetch successful"

        # Step 2: Read current value
        local current_id
        current_id=$(git show "origin/$BRANCH:$COUNTER_FILE" 2>/dev/null) || {
            die "Could not read $COUNTER_FILE from origin/$BRANCH. Branch may be corrupted."
        }

        # Trim whitespace
        current_id=$(echo "$current_id" | tr -d '[:space:]')
        debug "Current counter value: $current_id"

        # Validate it's a number
        if ! [[ "$current_id" =~ ^[0-9]+$ ]]; then
            die "Invalid counter value: '$current_id' (expected a number)"
        fi

        # Step 3: Compute new value. Normal claims only self-heal against
        # active task files; full active+archived repair is reserved for
        # --resync/setup so the common create path never scans archives.
        local claimed_id
        claimed_id=$(safe_claim_id_from_counter "$current_id")
        local new_id=$((claimed_id + 1))
        debug "Claiming ID $claimed_id, advancing counter from $current_id to $new_id"

        # Step 4: Create new commit via git plumbing
        local blob_hash tree_hash commit_hash parent_hash

        parent_hash=$(git rev-parse "origin/$BRANCH")
        blob_hash=$(echo "$new_id" | git hash-object -w --stdin)
        tree_hash=$(printf "100644 blob %s\t%s\n" "$blob_hash" "$COUNTER_FILE" | git mktree)
        commit_hash=$(echo "ait: Claim task ID t$claimed_id, advance counter to $new_id" | \
            git commit-tree "$tree_hash" -p "$parent_hash")

        # Step 5: Push - fails if another PC claimed simultaneously (non-fast-forward)
        debug "Pushing to origin..."
        if git push origin "$commit_hash:refs/heads/$BRANCH" 2>/dev/null; then
            # Keep local branch in sync with remote
            git update-ref "refs/heads/$BRANCH" "$commit_hash" 2>/dev/null || true
            debug "Push successful, claimed ID: $claimed_id"
            echo "$claimed_id"
            return 0
        fi

        # Push failed (race condition) - retry
        debug "Push failed (race condition)"
        if [[ $attempt -lt $MAX_RETRIES ]]; then
            warn "ID claim race detected (attempt $attempt/$MAX_RETRIES), retrying..." >&2
            sleep "0.$((RANDOM % 4 + 1))"
        fi
    done

    die "Failed to claim task ID after $MAX_RETRIES attempts. Try again later."
}

# --- Resync: repair counter against active + archived history ---

resync_local() {
    local desired_id current_id
    desired_id=$(full_repair_next_id)

    if ! has_local_branch; then
        init_local_branch >/dev/null 2>&1 || true
    fi

    current_id=$(git show "$BRANCH:$COUNTER_FILE" 2>/dev/null | tr -d '[:space:]') || {
        die "Could not read $COUNTER_FILE from local $BRANCH. Branch may be corrupted."
    }
    if ! [[ "$current_id" =~ ^[0-9]+$ ]]; then
        die "Invalid local counter value: '$current_id' (expected a number)"
    fi

    if [[ "$current_id" -ge "$desired_id" ]]; then
        echo "OK:$current_id"
        return 0
    fi

    commit_counter_value "refs/heads/$BRANCH" "$BRANCH" "$desired_id" \
        "ait: Resync local task ID counter to $desired_id" >/dev/null
    echo "RESYNCED:$current_id:$desired_id"
}

resync_counter() {
    if ! has_remote; then
        debug "No remote — resyncing local counter branch"
        resync_local
        return 0
    fi

    local attempt=0 desired_id
    desired_id=$(full_repair_next_id)

    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))

        local fetch_err
        if ! fetch_err=$(git fetch origin \
            "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" --quiet 2>&1 >/dev/null); then
            local rstate
            rstate=$(remote_branch_state)
            case "$rstate" in
                PRESENT)
                    die "Failed to fetch counter branch '$BRANCH' from origin: ${fetch_err:-unknown git fetch error}"
                    ;;
                ERROR:*)
                    die "Cannot reach origin to verify counter branch '$BRANCH': ${rstate#ERROR:}"
                    ;;
                *)
                    if try_push_local_to_remote; then
                        continue
                    fi
                    die "Counter branch '$BRANCH' is not initialized on origin and no local branch exists to upgrade. Run 'ait setup' to initialize the counter."
                    ;;
            esac
        fi

        local current_id
        current_id=$(git show "origin/$BRANCH:$COUNTER_FILE" 2>/dev/null | tr -d '[:space:]') || {
            die "Could not read $COUNTER_FILE from origin/$BRANCH. Branch may be corrupted."
        }
        if ! [[ "$current_id" =~ ^[0-9]+$ ]]; then
            die "Invalid counter value: '$current_id' (expected a number)"
        fi

        if [[ "$current_id" -ge "$desired_id" ]]; then
            git update-ref "refs/heads/$BRANCH" "origin/$BRANCH" 2>/dev/null || true
            echo "OK:$current_id"
            return 0
        fi

        local blob_hash tree_hash commit_hash parent_hash
        parent_hash=$(git rev-parse "origin/$BRANCH")
        blob_hash=$(echo "$desired_id" | git hash-object -w --stdin)
        tree_hash=$(printf "100644 blob %s\t%s\n" "$blob_hash" "$COUNTER_FILE" | git mktree)
        commit_hash=$(echo "ait: Resync task ID counter to $desired_id" | \
            git commit-tree "$tree_hash" -p "$parent_hash")

        if git push origin "$commit_hash:refs/heads/$BRANCH" 2>/dev/null; then
            git update-ref "refs/heads/$BRANCH" "$commit_hash" 2>/dev/null || true
            echo "RESYNCED:$current_id:$desired_id"
            return 0
        fi

        if [[ $attempt -lt $MAX_RETRIES ]]; then
            warn "ID counter resync race detected (attempt $attempt/$MAX_RETRIES), retrying..." >&2
            sleep "0.$((RANDOM % 4 + 1))"
        fi
    done

    die "Failed to resync task ID counter after $MAX_RETRIES attempts. Try again later."
}

# --- Peek: show current counter without claiming ---

peek_counter() {
    if ! has_remote; then
        if has_local_branch; then
            git show "$BRANCH:$COUNTER_FILE" 2>/dev/null | tr -d '[:space:]'
        else
            # No branch yet — show what next claim would return
            local max_id
            max_id=$(scan_max_task_id "$TASK_DIR" "$ARCHIVED_DIR")
            echo $((max_id + 1))
        fi
        return 0
    fi

    local fetch_err
    if ! fetch_err=$(git fetch origin \
        "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" --quiet 2>&1 >/dev/null); then
        local diagnostic rstate
        rstate=$(remote_branch_state)
        case "$rstate" in
            PRESENT)
                diagnostic="Failed to fetch counter branch '$BRANCH' from origin: ${fetch_err:-unknown git fetch error}"
                ;;
            ERROR:*)
                diagnostic="Cannot reach origin to verify counter branch '$BRANCH': ${rstate#ERROR:}"
                ;;
            *)
                diagnostic="Counter branch '$BRANCH' is not initialized on origin"
                ;;
        esac

        # Fall back to local branch if remote fetch fails.
        if has_local_branch; then
            warn "$diagnostic — showing local value" >&2
            git show "$BRANCH:$COUNTER_FILE" 2>/dev/null | tr -d '[:space:]'
            return 0
        fi

        case "$rstate" in
            ABSENT)
                die "$diagnostic and no local branch exists to read. Run 'ait setup' to initialize the counter."
                ;;
            *)
                die "$diagnostic"
                ;;
        esac
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
Usage: aitask_claim_id.sh [--debug] [--init|--claim|--peek|--resync]

Internal script for atomic task ID management.

When a git remote 'origin' is configured, uses a shared counter branch
for collision-free IDs across multiple PCs. When no remote is configured,
uses a local counter branch (auto-created on first claim). When a remote
is later added, the local branch is automatically pushed to remote.

Options:
  --init    Initialize the aitask-ids counter branch on remote
  --claim   Claim the next task ID (atomic if remote, local scan otherwise)
  --peek    Show current/next counter value without claiming
  --resync  Repair counter to max(active+archived task IDs)+1
  --debug   Enable verbose debug output
  --help    Show this help message
EOF
}

# Parse --debug flag first
while [[ "${1:-}" == "--debug" ]]; do
    DEBUG=true
    shift
done

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
    --resync|resync)
        resync_counter
        ;;
    --help|-h)
        show_help
        ;;
    *)
        die "Unknown option: $1. Use --help for usage."
        ;;
esac
