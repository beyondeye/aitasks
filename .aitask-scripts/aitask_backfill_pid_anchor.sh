#!/usr/bin/env bash
# aitask_backfill_pid_anchor.sh - One-shot helper that retrofits PID anchors
# onto pre-existing locks for tasks currently in `status: Implementing`.
#
# Why: t723 added pid:/pid_starttime: to lock YAML so re-pick can detect
# tmux/host-shell crashes via the new RECLAIM_CRASH: signal. Locks that
# existed before this change lack the fields, so re-pick falls back to
# the legacy RECLAIM_STATUS: branch (no PID-based crash signal). This
# script writes pid: 0 + pid_starttime: - into each pre-anchor lock so
# the next re-pick fires RECLAIM_CRASH: instead — a sharper signal that
# carries through to the case-specific crash-recovery prompt.
#
# Usage: ./.aitask-scripts/aitask_backfill_pid_anchor.sh
#
# Behavior:
#   - Lists all aitasks/*.md (and aitasks/t<N>/*.md) with status: Implementing.
#   - Fetches origin/aitask-locks once, then per-task git-show (no extra fetch).
#   - For each lock: skip if it already has `pid:`, skip if missing entirely,
#     otherwise rewrite with `pid: 0` + `pid_starttime: -` and stage it for
#     a single batch commit on aitask-locks.
#   - Pushes the rewritten branch.
#
# Safe to re-run: locks that already have pid: are skipped.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/pid_anchor.sh
source "$SCRIPT_DIR/lib/pid_anchor.sh"

BRANCH="aitask-locks"
TASK_DIR="${TASK_DIR:-aitasks}"
ARCHIVED_DIR="${ARCHIVED_DIR:-aitasks/archived}"

# --- Sentinel self-test ---
# We use pid: 0 as the "unknown / crashed" sentinel. is_lock_holder_alive
# explicitly rejects "0" via its leading guard, so this would always be
# treated as crashed regardless of `kill -0 0` behavior. The guard exists
# so we don't depend on platform-specific `kill -0 0` semantics.
SENTINEL_PID="0"
if is_lock_holder_alive "$SENTINEL_PID" "-"; then
    die "PID-anchor sentinel self-test failed: pid:0 reports alive. Aborting."
fi

# --- Find Implementing tasks ---
find_implementing_tasks() {
    # Scan parent and child task files (excluding archived). Print task IDs
    # one per line (parent: "12", child: "12_3").
    local task_file task_id
    while IFS= read -r -d '' task_file; do
        if grep -q '^status: Implementing' "$task_file" 2>/dev/null; then
            local stem
            stem=$(basename "$task_file" .md)
            # stem is t<N> or t<parent>_<child>; strip leading t and the
            # trailing _<description> by taking only digit-and-underscore
            # leading portion.
            task_id=$(echo "$stem" | sed -E 's/^t([0-9]+(_[0-9]+)?).*/\1/')
            echo "$task_id"
        fi
    done < <(find -L "$TASK_DIR" -path "$ARCHIVED_DIR" -prune -o -type f -name 't*.md' -print0)
}

# --- Main ---

main() {
    if ! git remote get-url origin &>/dev/null; then
        die "No 'origin' remote configured."
    fi

    info "Fetching $BRANCH from origin..."
    if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
        die "Failed to fetch $BRANCH from origin (network or branch missing)."
    fi

    local parent_hash current_tree_hash
    if ! parent_hash=$(git rev-parse "origin/$BRANCH" 2>/dev/null); then
        die "$BRANCH does not exist on origin. Run 'ait setup' to initialize."
    fi
    current_tree_hash=$(git rev-parse "origin/$BRANCH^{tree}")

    local implementing_ids
    implementing_ids=$(find_implementing_tasks | sort -u)

    if [[ -z "$implementing_ids" ]]; then
        info "No tasks with status: Implementing found."
        echo "Backfilled 0 locks; 0 already had PID anchors; 0 locks missing."
        return 0
    fi

    info "Implementing tasks found:"
    while IFS= read -r tid; do
        info "  - t$tid"
    done <<<"$implementing_ids"

    local backfilled=0 already_anchored=0 missing=0
    local new_tree_hash="$current_tree_hash"

    while IFS= read -r tid; do
        local lock_file="t${tid}_lock.yaml"
        local lock_content=""

        if ! git ls-tree "$current_tree_hash" -- "$lock_file" 2>/dev/null | grep -q "$lock_file"; then
            warn "  t$tid: lock file missing on $BRANCH (RECLAIM_STATUS will handle on next pick)"
            missing=$((missing + 1))
            continue
        fi

        lock_content=$(git show "origin/$BRANCH:$lock_file" 2>/dev/null || true)
        if [[ -z "$lock_content" ]]; then
            warn "  t$tid: lock file present but empty (skipping)"
            missing=$((missing + 1))
            continue
        fi

        if echo "$lock_content" | grep -q '^pid:'; then
            info "  t$tid: lock already has pid: anchor (skipping)"
            already_anchored=$((already_anchored + 1))
            continue
        fi

        # Rewrite with sentinel anchor. Preserve all existing fields and
        # append pid:/pid_starttime: at the end.
        local new_yaml
        new_yaml="${lock_content}
pid: ${SENTINEL_PID}
pid_starttime: -"

        local blob_hash
        blob_hash=$(echo "$new_yaml" | git hash-object -w --stdin)

        # Rebuild tree with the new blob for this lock.
        new_tree_hash=$( {
            git ls-tree "$new_tree_hash" | grep -v "	${lock_file}$" || true
            printf "100644 blob %s\t%s\n" "$blob_hash" "$lock_file"
        } | git mktree )

        info "  t$tid: backfilling pid: $SENTINEL_PID anchor"
        backfilled=$((backfilled + 1))
    done <<<"$implementing_ids"

    if [[ $backfilled -eq 0 ]]; then
        info "Nothing to commit."
        echo "Backfilled 0 locks; $already_anchored already had PID anchors; $missing locks missing entirely (RECLAIM_STATUS will handle)."
        return 0
    fi

    local commit_msg="ait: Backfill PID anchor for $backfilled Implementing lock(s)"
    local commit_hash_new
    commit_hash_new=$(echo "$commit_msg" | git commit-tree "$new_tree_hash" -p "$parent_hash")

    info "Pushing rewritten $BRANCH..."
    if git push origin "$commit_hash_new:refs/heads/$BRANCH" 2>/dev/null; then
        success "Pushed backfill commit to $BRANCH."
    else
        die "Push failed. Another lock operation may have raced — re-run the script."
    fi

    echo "Backfilled $backfilled lock(s); $already_anchored already had PID anchors; $missing locks missing entirely (RECLAIM_STATUS will handle)."
}

main "$@"
