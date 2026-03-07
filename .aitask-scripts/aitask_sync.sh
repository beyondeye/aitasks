#!/usr/bin/env bash
# aitask_sync.sh - Bidirectional sync of task data with remote
#
# Supports both data-branch mode (.aitask-data worktree) and legacy mode
# (tasks on main branch). Auto-commits uncommitted task changes, fetches,
# rebases, and pushes.
#
# Usage:
#   ./aiscripts/aitask_sync.sh            # Interactive mode (colored output)
#   ./aiscripts/aitask_sync.sh --batch    # Structured output for scripting
#
# Batch output protocol (single line on stdout):
#   SYNCED                     Both push and pull completed
#   PUSHED                     Local changes pushed, nothing to pull
#   PULLED                     Remote changes pulled, nothing to push
#   NOTHING                    Already up-to-date
#   CONFLICT:<file1>,<file2>   Merge conflicts detected (rebase aborted)
#   AUTOMERGED                 Conflicts detected but all auto-resolved
#   NO_NETWORK                 Fetch/push timed out or failed
#   NO_REMOTE                  No remote configured
#   ERROR:<message>            Unexpected error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Configuration ---
BATCH_MODE=false
NETWORK_TIMEOUT=10

# --- Auto-merge support (best-effort) ---
_MERGE_PYTHON=""
_MERGE_SCRIPT="$SCRIPT_DIR/board/aitask_merge.py"
_init_merge_python() {
    local venv_py="$HOME/.aitask/venv/bin/python"
    if [[ -x "$venv_py" ]]; then
        _MERGE_PYTHON="$venv_py"
    elif command -v python3 &>/dev/null; then
        _MERGE_PYTHON="python3"
    fi
}
_init_merge_python

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_sync.sh [options]

Sync task data with remote: auto-commit local changes, fetch, rebase,
and push. Works in both data-branch mode (.aitask-data worktree) and
legacy mode (tasks on main branch).

Options:
  --batch       Structured output for scripting (no colors, no prompts)
  --help, -h    Show this help

Interactive mode:
  Shows colored progress messages. On merge conflicts, opens $EDITOR
  (default: nano) for each conflicted file, then continues the rebase.

Batch output protocol (single line on stdout):
  SYNCED                     Both push and pull completed
  PUSHED                     Local changes pushed, nothing to pull
  PULLED                     Remote changes pulled, nothing to push
  NOTHING                    Already up-to-date
  CONFLICT:<file1>,<file2>   Merge conflicts (rebase aborted in batch)
  AUTOMERGED                 Conflicts detected but all auto-resolved
  NO_NETWORK                 Fetch/push timed out or failed
  NO_REMOTE                  No remote configured
  ERROR:<message>            Unexpected error
EOF
}

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --batch)  BATCH_MODE=true; shift ;;
        --help|-h) show_help; exit 0 ;;
        *) die "Unknown option: $1. Use --help for usage." ;;
    esac
done

# --- Portable timeout wrapper ---
# Uses coreutils timeout if available, falls back to background process watchdog.
# Returns 124 on timeout (same as coreutils timeout).
# Note: Cannot use `timeout task_git` because task_git is a shell function.
# Instead, we build the raw git command args respecting the data worktree.
_git_with_timeout() {
    _ait_detect_data_worktree
    local git_args=()
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git_args=(-C "$_AIT_DATA_WORKTREE")
    fi
    git_args+=("$@")

    if command -v timeout &>/dev/null; then
        timeout "$NETWORK_TIMEOUT" git "${git_args[@]}"
    else
        # macOS fallback: background process with watchdog
        git "${git_args[@]}" &
        local pid=$!
        local i=0
        while kill -0 "$pid" 2>/dev/null && [[ $i -lt $NETWORK_TIMEOUT ]]; do
            sleep 1
            i=$((i + 1))
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
            return 124
        fi
        wait "$pid"
    fi
}

# --- Output helpers ---
batch_out() {
    if [[ "$BATCH_MODE" == true ]]; then
        echo "$1"
    fi
}

# Only show interactive messages in non-batch mode
iinfo() {
    if [[ "$BATCH_MODE" == false ]]; then
        info "$1"
    fi
}

iwarn() {
    if [[ "$BATCH_MODE" == false ]]; then
        warn "$1"
    fi
}

isuccess() {
    if [[ "$BATCH_MODE" == false ]]; then
        success "$1"
    fi
}

# --- Check for remote ---
check_remote() {
    if ! task_git remote get-url origin &>/dev/null; then
        batch_out "NO_REMOTE"
        if [[ "$BATCH_MODE" == false ]]; then
            warn "No remote configured"
        fi
        exit 0
    fi
}

# --- Auto-commit uncommitted task/plan changes ---
auto_commit() {
    local dirty
    dirty=$(task_git status --porcelain -- aitasks/ aiplans/ 2>/dev/null || true)
    if [[ -z "$dirty" ]]; then
        return 0
    fi

    local file_count
    file_count=$(echo "$dirty" | wc -l | tr -d ' ')
    iinfo "Auto-committing $file_count modified task/plan files..."

    task_git add aitasks/ aiplans/ 2>/dev/null || true
    task_git commit -m "ait: Auto-commit task changes before sync" --quiet 2>/dev/null || true
}

# --- Fetch with timeout ---
do_fetch() {
    iinfo "Fetching from remote..."
    local fetch_exit=0
    _git_with_timeout fetch origin 2>/dev/null || fetch_exit=$?

    if [[ $fetch_exit -eq 124 ]]; then
        batch_out "NO_NETWORK"
        if [[ "$BATCH_MODE" == false ]]; then
            warn "Network timeout during fetch"
        fi
        exit 0
    elif [[ $fetch_exit -ne 0 ]]; then
        batch_out "NO_NETWORK"
        if [[ "$BATCH_MODE" == false ]]; then
            warn "Fetch failed (no network?)"
        fi
        exit 0
    fi
}

# --- Count commits ahead/behind ---
count_local_ahead() {
    task_git rev-list --count "@{u}..HEAD" 2>/dev/null || echo "0"
}

count_remote_ahead() {
    task_git rev-list --count "HEAD..@{u}" 2>/dev/null || echo "0"
}

# --- Auto-merge conflicted task/plan files ---
# try_auto_merge <conflicted_files_newline_separated>
# Attempts auto-merge for each task/plan file using Python merge script.
# Outputs remaining unresolved files (newline-separated) to stdout.
# Returns 0 if ALL resolved, 1 if any remain unresolved.
try_auto_merge() {
    local conflicted="$1"
    local unresolved=""
    local resolved_count=0

    if [[ -z "$_MERGE_PYTHON" ]] || [[ ! -f "$_MERGE_SCRIPT" ]]; then
        echo "$conflicted"
        return 1
    fi

    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        case "$f" in
            aitasks/*.md|aiplans/*.md)
                local file_path merge_exit=0
                file_path="$(_resolve_conflict_path "$f")"
                PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SCRIPT_DIR/board" "$_MERGE_PYTHON" "$_MERGE_SCRIPT" "$file_path" --batch --rebase 2>/dev/null || merge_exit=$?
                if [[ $merge_exit -eq 0 ]]; then
                    task_git add "$f" 2>/dev/null || true
                    resolved_count=$((resolved_count + 1))
                    iinfo "Auto-merged: $f"
                else
                    unresolved="${unresolved}${unresolved:+$'\n'}$f"
                fi
                ;;
            *)
                unresolved="${unresolved}${unresolved:+$'\n'}$f"
                ;;
        esac
    done <<< "$conflicted"

    if [[ -z "$unresolved" ]]; then
        iinfo "Auto-merged $resolved_count file(s)"
        return 0
    else
        [[ $resolved_count -gt 0 ]] && iinfo "Auto-merged $resolved_count file(s), remaining conflicts need manual resolution"
        echo "$unresolved"
        return 1
    fi
}

# --- Rebase advancement helper ---
# Try rebase --continue, fall back to --skip for empty patches (when
# auto-merge result matches the current HEAD exactly, git sees "nothing to commit").
_rebase_advance() {
    if GIT_EDITOR=true task_git rebase --continue &>/dev/null; then
        return 0
    fi
    # If no unresolved files remain, this is an empty patch — skip it
    local unresolved
    unresolved=$(task_git diff --name-only --diff-filter=U 2>/dev/null || true)
    if [[ -z "$unresolved" ]] && task_git rebase --skip &>/dev/null; then
        return 0
    fi
    return 1
}

# --- Pull with rebase ---
# Returns: 0 = normal pull, 1 = failure, 2 = automerged
_PULL_AUTOMERGED=false
do_pull_rebase() {
    local remote_count="$1"
    iinfo "Pulling $remote_count new commits (rebase)..."

    local pull_exit=0
    task_git pull --rebase --quiet &>/dev/null || pull_exit=$?

    if [[ $pull_exit -ne 0 ]]; then
        # Check if it's a conflict
        local conflicted
        conflicted=$(task_git diff --name-only --diff-filter=U 2>/dev/null || true)

        if [[ -n "$conflicted" ]]; then
            # Try auto-merge first
            local remaining=""
            local merge_rc=1
            remaining=$(try_auto_merge "$conflicted") && merge_rc=0 || merge_rc=$?

            if [[ $merge_rc -eq 0 ]]; then
                # All conflicts auto-resolved — advance rebase (may loop for multi-commit)
                local continue_ok=true
                while true; do
                    if _rebase_advance; then
                        break  # rebase complete
                    fi
                    # Check for new conflicts from next commit
                    local new_conflicted
                    new_conflicted=$(task_git diff --name-only --diff-filter=U 2>/dev/null || true)
                    if [[ -n "$new_conflicted" ]]; then
                        local new_remaining=""
                        local new_merge_rc=1
                        new_remaining=$(try_auto_merge "$new_conflicted") && new_merge_rc=0 || new_merge_rc=$?
                        if [[ $new_merge_rc -ne 0 ]]; then
                            # Can't auto-merge this round
                            if [[ "$BATCH_MODE" == true ]]; then
                                task_git rebase --abort 2>/dev/null || true
                                local conflict_list
                                conflict_list=$(echo "$new_remaining" | tr '\n' ',' | sed 's/,$//')
                                batch_out "CONFLICT:${conflict_list}"
                                exit 0
                            else
                                warn "Auto-merged earlier commits, but new conflicts in:"
                                echo "$new_remaining" | while IFS= read -r f; do echo "  - $f"; done
                                remaining="$new_remaining"
                                continue_ok=false
                                break
                            fi
                        fi
                        # new conflicts also auto-merged, loop to advance rebase
                    else
                        # rebase advance failed for non-conflict reason
                        task_git rebase --abort 2>/dev/null || true
                        batch_out "ERROR:rebase_continue_failed"
                        return 1
                    fi
                done

                if [[ "$continue_ok" == true ]]; then
                    _PULL_AUTOMERGED=true
                    isuccess "All conflicts auto-merged successfully"
                    return 0
                fi
                # If continue_ok=false, fall through to interactive handling with $remaining
            fi

            # Some files unresolved (or auto-merge unavailable)
            if [[ "$BATCH_MODE" == true ]]; then
                task_git rebase --abort 2>/dev/null || true
                local conflict_list
                conflict_list=$(echo "$remaining" | tr '\n' ',' | sed 's/,$//')
                batch_out "CONFLICT:${conflict_list}"
                exit 0
            else
                # Interactive conflict resolution with remaining files only
                warn "Remaining conflicts in:"
                echo "$remaining" | while IFS= read -r f; do echo "  - $f"; done

                local editor="${EDITOR:-nano}"
                echo ""
                info "Opening each conflicted file in $editor for resolution..."

                local all_resolved=true
                echo "$remaining" | while IFS= read -r f; do
                    [[ -z "$f" ]] && continue
                    echo ""
                    info "Editing: $f"
                    if $editor "$(_resolve_conflict_path "$f")"; then
                        task_git add "$f" 2>/dev/null || true
                    else
                        warn "Editor exited with error for $f"
                        all_resolved=false
                    fi
                done

                if [[ "$all_resolved" == true ]]; then
                    if ! _rebase_advance; then
                        warn "Rebase continue failed. Aborting rebase."
                        task_git rebase --abort 2>/dev/null || true
                        return 1
                    fi
                else
                    warn "Not all conflicts resolved. Aborting rebase."
                    task_git rebase --abort 2>/dev/null || true
                    return 1
                fi
            fi
        else
            # Not a conflict — some other pull/rebase error
            task_git rebase --abort 2>/dev/null || true
            batch_out "ERROR:pull_rebase_failed"
            if [[ "$BATCH_MODE" == false ]]; then
                warn "Pull --rebase failed (non-conflict error)"
            fi
            return 1
        fi
    fi
    return 0
}

# Resolve the file path for editing during conflict resolution
_resolve_conflict_path() {
    local file="$1"
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        echo "$_AIT_DATA_WORKTREE/$file"
    else
        echo "$file"
    fi
}

# --- Push with retry ---
do_push() {
    local local_count="$1"
    iinfo "Pushing $local_count commits to remote..."

    local push_exit=0
    _git_with_timeout push origin 2>/dev/null || push_exit=$?

    if [[ $push_exit -eq 124 ]]; then
        batch_out "NO_NETWORK"
        if [[ "$BATCH_MODE" == false ]]; then
            warn "Network timeout during push"
        fi
        exit 0
    elif [[ $push_exit -ne 0 ]]; then
        # Retry once (remote may have advanced during our rebase)
        iinfo "Push rejected, retrying after fetch+rebase..."
        _git_with_timeout fetch origin 2>/dev/null || true
        task_git pull --rebase --quiet 2>/dev/null || true
        local retry_exit=0
        _git_with_timeout push origin 2>/dev/null || retry_exit=$?

        if [[ $retry_exit -ne 0 ]]; then
            batch_out "ERROR:push_failed"
            if [[ "$BATCH_MODE" == false ]]; then
                warn "Push failed after retry"
            fi
            return 1
        fi
    fi
    return 0
}

# --- Main ---
main() {
    # Step 1: Detect mode
    _ait_detect_data_worktree

    # Step 2: Check for remote
    check_remote

    # Step 3: Auto-commit uncommitted changes
    auto_commit

    # Step 4: Count local-ahead commits
    local local_ahead
    local_ahead=$(count_local_ahead)

    # Step 5: Fetch with timeout
    do_fetch

    # Step 6: Count remote-ahead commits
    local remote_ahead
    remote_ahead=$(count_remote_ahead)

    # Step 7: Pull rebase if remote has commits
    local did_pull=false
    if [[ "$remote_ahead" -gt 0 ]]; then
        if do_pull_rebase "$remote_ahead"; then
            did_pull=true
        else
            # Pull failed (non-batch conflict resolution or error)
            exit 1
        fi
    fi

    # Step 8: Push if local has commits (recount after possible rebase)
    local did_push=false
    local_ahead=$(count_local_ahead)
    if [[ "$local_ahead" -gt 0 ]]; then
        if do_push "$local_ahead"; then
            did_push=true
        else
            exit 1
        fi
    fi

    # Step 9: Output result
    if [[ "$_PULL_AUTOMERGED" == true ]]; then
        batch_out "AUTOMERGED"
        isuccess "Sync complete: conflicts auto-merged"
    elif [[ "$did_push" == true && "$did_pull" == true ]]; then
        batch_out "SYNCED"
        isuccess "Sync complete: pushed and pulled changes"
    elif [[ "$did_push" == true ]]; then
        batch_out "PUSHED"
        isuccess "Sync complete: pushed $local_ahead commits"
    elif [[ "$did_pull" == true ]]; then
        batch_out "PULLED"
        isuccess "Sync complete: pulled $remote_ahead commits"
    else
        batch_out "NOTHING"
        isuccess "Already up to date"
    fi
}

main
