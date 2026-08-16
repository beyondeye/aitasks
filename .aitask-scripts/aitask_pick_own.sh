#!/usr/bin/env bash
# aitask_pick_own.sh - Claim ownership of a task (sync, lock, update status, commit, push)
#
# Consolidates Step 4 of the task-workflow skill into a single script call.
# The calling LLM handles email selection interactively, then passes the
# chosen email here for lock acquisition, metadata update, and git operations.
#
# Also supports a sync-only mode (--sync) for pre-task-selection sync,
# replacing the manual git pull + lock cleanup commands in calling skills.
#
# Usage:
#   ./.aitask-scripts/aitask_pick_own.sh <task_id> [--email <email>]   # Full ownership
#   ./.aitask-scripts/aitask_pick_own.sh <task_id> --force --email <e>  # Override a held lock
#   ./.aitask-scripts/aitask_pick_own.sh --sync                         # Sync-only mode
#
# Output format (structured lines for LLM parsing):
#   OWNED:<task_id>              Task successfully claimed
#   LOCK_FAILED:<owner>|<locked_at>|<hostname>   Lock held by another user (exit 1)
#   LOCK_LIVE_HOLDER:<owner>|<locked_at>|<hostname>|<pid>
#                                Lock held by ANOTHER LIVE SESSION of yours on
#                                this host (exit 1). Nothing was claimed: the
#                                refusal happens before the lock, the status
#                                write and the commit, so there is nothing to
#                                give back. Re-run with --force to take it.
#   LOCK_UNVERIFIABLE_HOLDER:<owner>|<locked_at>|<hostname>|<pid>
#                                Same, but the holder's liveness could not be
#                                established ("cannot tell" is its own state,
#                                never rounded to alive or dead). Also exit 1.
#   LOCK_INFRA_MISSING           Lock infrastructure not initialized (exit 1)
#   LOCK_ERROR:<message>         Lock system error (exit 1)
#   FORCE_UNLOCKED:<prev_owner>  Prior lock force-unlocked, then re-locked
#   SYNCED                       Sync-only mode completed (pulled, already up to
#                                date, or no remote configured)
#   SYNC_FAILED:<reason>         Sync-only mode: the pull failed; <reason> is a
#                                task_utils.sh classifier code (dirty_worktree,
#                                rebase_conflict, no_upstream,
#                                remote_unreachable, diverged, unknown).
#                                Still exits 0 — sync is best-effort; details
#                                and a recovery hint go to stderr.
#
# Stale-lock cleanup runs alongside the pull in both modes and is likewise
# best-effort: a failed sweep never blocks a pick (this script still exits 0 and
# --sync still prints SYNCED / SYNC_FAILED), but it is no longer silent —
# aitask_lock.sh's own diagnosis is forwarded to stderr together with a warning
# naming the consequence. Successful and nothing-to-do sweeps stay silent.
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
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/pid_anchor.sh
source "$SCRIPT_DIR/lib/pid_anchor.sh"

# --- Configuration ---
TASK_ID=""
EMAIL=""
SYNC_ONLY=false
FORCE=false
EMAILS_FILE="aitasks/metadata/emails.txt"

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_pick_own.sh [options] <task_id>
       aitask_pick_own.sh --sync

Claim ownership of a task: sync remote, acquire lock, set status to
Implementing, commit and push. In sync-only mode, just pull and clean
up stale locks.

Arguments:
  task_id         Task number: 166 or t166 (parent), 16_2 or t16_2 (child)
                  Not required in --sync mode.

Options:
  --email EMAIL   Email of the person claiming the task. If provided and new,
                  it is stored to aitasks/metadata/emails.txt (deduplicated).
  --force         Claim the task even though the lock is already held:
                  by another user, or by another session of your own on this
                  host that is still running or cannot be verified as gone
                  (see LOCK_LIVE_HOLDER / LOCK_UNVERIFIABLE_HOLDER below).
                  The lock is released and re-taken. Requires --email.
                  Only pass this on an explicit human decision — forcing past
                  a LIVE holder leaves two agents working one task.
  --sync          Sync-only mode: git pull + stale lock cleanup, then exit.
                  No task_id required.
  --help, -h      Show this help

Output format (one structured line to stdout):
  OWNED:<task_id>              Task successfully claimed
  LOCK_FAILED:<owner>|<locked_at>|<hostname>
                               Lock held by another user (exit 1)
  LOCK_LIVE_HOLDER:<owner>|<locked_at>|<hostname>|<pid>
                               Held by another session of YOURS on this host
                               that is still running (exit 1). Nothing was
                               claimed — the refusal precedes the lock, the
                               status write and the commit. Overridable with
                               --force.
  LOCK_UNVERIFIABLE_HOLDER:<owner>|<locked_at>|<hostname>|<pid>
                               Same, but the holder could not be shown to be
                               either running or gone (exit 1). Also
                               overridable with --force.
  LOCK_INFRA_MISSING           Lock infrastructure not initialized (exit 1)
  LOCK_ERROR:<message>         Lock system error (exit 1)
  FORCE_UNLOCKED:<prev_owner>  Prior lock force-unlocked, then re-locked
  SYNCED                       Sync-only mode completed

Full ownership mode performs these steps in order:
  1. git pull --ff-only (best-effort sync with remote)
  2. Stale lock cleanup (best-effort)
  3. Store email to emails.txt if provided (deduplicated)
  4. Acquire atomic lock via aitask_lock.sh
  5. Update task status to Implementing via aitask_update.sh
  6. git add + commit + push (push is best-effort)

Examples:
  ./.aitask-scripts/aitask_pick_own.sh 166 --email "user@example.com"
  ./.aitask-scripts/aitask_pick_own.sh t16_2 --email "user@example.com"
  ./.aitask-scripts/aitask_pick_own.sh 166          # No email (skip lock)
  ./.aitask-scripts/aitask_pick_own.sh --sync       # Sync-only mode
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
            --force)
                FORCE=true
                shift
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

# Outcome of the most recent lock_cleanup call. Like task_sync, lock_cleanup
# always returns 0 — a failed sweep must never block a pick — so read these
# when the outcome matters.
LOCK_CLEANUP_STATUS=""   # ok | failed
LOCK_CLEANUP_REASON=""   # branch_unreadable | push_failed | invoke_failed

# --- Sync with remote (best-effort) ---
sync_remote() {
    task_sync
    lock_cleanup
}

# Sweep locks abandoned by finished sessions. Best-effort but never silent:
# a swallowed failure lets stale locks pile up until a later pick reports
# LOCK_FAILED for a task nobody is actually working on.
# shellcheck disable=SC2034  # the LOCK_CLEANUP_* globals ARE the return value; they are read by tests and by callers that care about the outcome
lock_cleanup() {
    LOCK_CLEANUP_STATUS=""
    LOCK_CLEANUP_REASON=""

    local out="" rc=0
    # Combined capture: on success the child's progress notices are dropped
    # (our stdout is a machine contract, and a successful housekeeping sweep is
    # not worth reporting); on failure everything it said is forwarded.
    out="$("$SCRIPT_DIR/aitask_lock.sh" --cleanup 2>&1)" || rc=$?

    if [[ $rc -eq 0 ]]; then
        LOCK_CLEANUP_STATUS="ok"
        return 0
    fi

    LOCK_CLEANUP_STATUS="failed"
    case $rc in
        11) LOCK_CLEANUP_REASON="branch_unreadable" ;;
        12) LOCK_CLEANUP_REASON="push_failed" ;;
        *)  LOCK_CLEANUP_REASON="invoke_failed" ;;
    esac
    [[ -n "$out" ]] && printf '%s\n' "$out" >&2
    _lock_cleanup_warn "$rc"
    return 0
}

# Internal: name the consequence. aitask_lock.sh already reported the specific
# git failure (forwarded above); this adds why the user should care.
_lock_cleanup_warn() {
    local rc="$1" what
    case "$LOCK_CLEANUP_REASON" in
        branch_unreadable) what="stale lock cleanup did not complete" ;;
        push_failed)       what="stale locks could not be removed" ;;
        *)                 what="stale lock cleanup failed (aitask_lock.sh --cleanup exited ${rc})" ;;
    esac
    warn "${what} — locks abandoned by finished sessions may persist, and a later pick can report LOCK_FAILED for a task nobody is working on; inspect with './ait lock --list'"
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
# Returns: 0=success, 1=lock held by other (LOCK_FAILED printed),
#          2=infra missing (LOCK_INFRA_MISSING printed), 3=other error (LOCK_ERROR printed),
#          4=live session of ours holds it (LOCK_LIVE_HOLDER printed),
#          5=holder's liveness undecidable (LOCK_UNVERIFIABLE_HOLDER printed)
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
        # Forward LOCK_RECLAIM: signal (same-email-different-host re-lock)
        # and PRIOR_LOCK: (PID anchor info from prior lock — used by main()
        # to decide RECLAIM_CRASH vs. RECLAIM_STATUS) to our caller.
        echo "$lock_output" | grep -E '^(LOCK_RECLAIM|PRIOR_LOCK):' || true
        # Our stdout is a machine contract, so the lock script's chatter is
        # dropped — but a WARNING is a diagnostic the user must still see.
        # It goes to stderr, which cannot corrupt that contract. Without this
        # the "AIT_AGENT_PID does not name a live process" notice from
        # lib/pid_anchor.sh was captured into $lock_output and silently
        # discarded, i.e. a broken launcher anchor failed invisibly (t1465).
        echo "$lock_output" | grep -i 'warning:' >&2 || true
        return 0
    fi

    case $lock_exit in
        1)  # Already locked by another user
            local holder_line owner locked_at locked_hostname
            holder_line=$(echo "$lock_output" | grep '^LOCK_HOLDER:' || true)
            if [[ -n "$holder_line" ]]; then
                local details="${holder_line#LOCK_HOLDER:}"
                owner=$(echo "$details" | cut -d'|' -f1)
                locked_at=$(echo "$details" | cut -d'|' -f2)
                locked_hostname=$(echo "$details" | cut -d'|' -f3)
            else
                owner=$(echo "$lock_output" | grep -o 'already locked by [^ ]*' | sed 's/already locked by //')
                locked_at="unknown"
                locked_hostname="unknown"
            fi
            [[ -z "$owner" ]] && owner="unknown"
            echo "LOCK_FAILED:${owner}|${locked_at}|${locked_hostname}"
            return 1 ;;
        10) echo "LOCK_INFRA_MISSING"; return 2 ;;
        11) echo "LOCK_ERROR:fetch_failed"; return 3 ;;
        12) echo "LOCK_ERROR:race_exhaustion"; return 3 ;;
        13|14)  # Same-host, same-email acquire gate (t1466). The lock script
                # already printed the structured line and refused BEFORE
                # writing anything; forward it verbatim and let main() decide
                # whether --force applies.
            local gate_line
            gate_line=$(echo "$lock_output" \
                | grep -E '^LOCK_(LIVE|UNVERIFIABLE)_HOLDER:' || true)
            if [[ -n "$gate_line" ]]; then
                echo "$gate_line"
            elif [[ $lock_exit -eq 13 ]]; then
                echo "LOCK_LIVE_HOLDER:unknown|unknown|unknown|-"
            else
                echo "LOCK_UNVERIFIABLE_HOLDER:unknown|unknown|unknown|-"
            fi
            # Plain `if`, not `[[ … ]] && return 4`: under `set -e` an AND-list
            # whose test fails takes the list's non-zero status and kills the
            # function before the fallback return is reached.
            if [[ $lock_exit -eq 13 ]]; then
                return 4
            fi
            return 5 ;;
        *)  echo "LOCK_ERROR:unknown"; return 3 ;;
    esac
}

# --- Force-acquire lock (unlock then re-lock) ---
# Returns: 0=success (FORCE_UNLOCKED printed), 3=error (LOCK_ERROR printed)
force_acquire_lock() {
    local task_id="$1"
    local email="$2"

    if [[ -z "$email" ]]; then
        return 0
    fi

    # Check who currently holds the lock
    local check_output previous_owner
    check_output=$("$SCRIPT_DIR/aitask_lock.sh" --check "$task_id" 2>&1) || true
    previous_owner=$(echo "$check_output" | grep '^locked_by:' | sed 's/locked_by: *//')
    [[ -z "$previous_owner" ]] && previous_owner="unknown"

    # Force unlock then re-lock
    "$SCRIPT_DIR/aitask_lock.sh" --unlock "$task_id" 2>/dev/null || true

    local lock_output lock_exit=0
    lock_output=$("$SCRIPT_DIR/aitask_lock.sh" --lock "$task_id" --email "$email" 2>&1) || lock_exit=$?

    if [[ $lock_exit -eq 0 ]]; then
        echo "FORCE_UNLOCKED:$previous_owner"
        return 0
    fi
    echo "LOCK_ERROR:force_lock_failed"
    return 3
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

    task_git add aitasks/

    # Only commit if there are staged changes (idempotent re-run safety)
    if task_git diff --cached --quiet; then
        info "No changes to commit (task may already be in Implementing status)"
    else
        task_git commit -m "ait: Start work on t${task_id}: set status to Implementing" --quiet
    fi

    # Push is best-effort — network failure should not block the workflow
    task_push
}

# --- Main ---
main() {
    parse_args "$@"

    # Step 1: Sync with remote (both modes)
    sync_remote

    # Sync-only mode: done. Report the real outcome — a failed sync used to be
    # indistinguishable from a successful one here (always "SYNCED").
    if [[ "$SYNC_ONLY" == true ]]; then
        if [[ "$TASK_SYNC_STATUS" == "failed" ]]; then
            echo "SYNC_FAILED:${TASK_SYNC_REASON}"
        else
            echo "SYNCED"
        fi
        return 0
    fi

    # Step 1b: Resolve email from task metadata or userconfig if not provided
    local task_file=""
    task_file=$(resolve_task_file "$TASK_ID" 2>/dev/null) || true
    if [[ -z "$EMAIL" ]]; then
        # Try assigned_to from the task file's frontmatter
        if [[ -n "$task_file" && -f "$task_file" ]]; then
            EMAIL=$(grep '^assigned_to:' "$task_file" 2>/dev/null | sed 's/assigned_to: *//' || true)
        fi
        # Fall back to userconfig.yaml
        if [[ -z "$EMAIL" ]]; then
            EMAIL=$(get_user_email)
        fi
    fi

    # Step 1c: Capture prior status for self-reclaim detection.
    # If the task was already in Implementing assigned to this email, the
    # caller (task-workflow Step 4) surfaces a reclaim prompt — even if the
    # lock branch is missing or out of sync (the LOCK_RECLAIM: path in
    # acquire_lock cannot see this case).
    local prev_status="" prev_assigned=""
    if [[ -n "$task_file" && -f "$task_file" ]]; then
        prev_status=$(grep '^status:' "$task_file" 2>/dev/null | sed 's/status: *//' || true)
        prev_assigned=$(grep '^assigned_to:' "$task_file" 2>/dev/null | sed 's/assigned_to: *//' || true)
    fi

    # Step 2: Store email if provided
    if [[ -n "$EMAIL" ]]; then
        store_email "$EMAIL"
    fi

    # Step 3: Acquire lock — capture stdout so we can parse PRIOR_LOCK:
    # before it's lost. Forward the captured output verbatim to our caller.
    local lock_result=0 acquire_stdout=""
    acquire_stdout=$(acquire_lock "$TASK_ID" "$EMAIL") || lock_result=$?
    [[ -n "$acquire_stdout" ]] && echo "$acquire_stdout"

    # 1 = another user's lock; 4/5 = our own email, but a different session on
    # this host that is live (4) or undecidable (5). All three are overridable
    # the same way, and force_acquire_lock unlocks first — so the re-lock sees
    # no prior lock and the acquire gate cannot re-fire.
    local forced_takeover=false
    if [[ ( $lock_result -eq 1 || $lock_result -eq 4 || $lock_result -eq 5 ) \
          && "$FORCE" == true ]]; then
        local force_result=0
        force_acquire_lock "$TASK_ID" "$EMAIL" || force_result=$?
        if [[ $force_result -ne 0 ]]; then
            exit 1
        fi
        forced_takeover=true
    elif [[ $lock_result -eq 1 || $lock_result -eq 4 || $lock_result -eq 5 ]]; then
        # LOCK_FAILED / LOCK_LIVE_HOLDER / LOCK_UNVERIFIABLE_HOLDER already
        # printed by acquire_lock. Nothing was claimed — the gate refuses
        # before the lock write, the status update and the commit — so there
        # is no state to roll back here.
        exit 1
    elif [[ $lock_result -eq 2 ]]; then
        # LOCK_INFRA_MISSING already printed by acquire_lock
        die "Run 'ait setup' to initialize lock infrastructure."
    elif [[ $lock_result -eq 3 ]]; then
        # LOCK_ERROR already printed by acquire_lock
        exit 1
    fi

    # Parse PRIOR_LOCK: from acquire output (one line; format
    # PRIOR_LOCK:<pid>|<starttime>|<host>|<locked_at>|<starttime_kind>).
    # Empty fields are "-". A 4-field line from a writer that predates the
    # kind field leaves prior_starttime_kind empty, which the ${…:-proc}
    # default below resolves the same way aitask_lock.sh does.
    local prior_pid="-" prior_starttime="-" prior_lock_host="-" prior_locked_at="-"
    local prior_starttime_kind=""
    local prior_line
    prior_line=$(echo "$acquire_stdout" | grep '^PRIOR_LOCK:' | head -1 || true)
    if [[ -n "$prior_line" ]]; then
        IFS='|' read -r prior_pid prior_starttime prior_lock_host prior_locked_at \
            prior_starttime_kind <<<"${prior_line#PRIOR_LOCK:}"
    fi

    # Step 4: Update task metadata
    update_task_status "$TASK_ID" "$EMAIL"

    # Step 5: Commit and push
    commit_and_push "$TASK_ID"

    # Output success
    echo "OWNED:$TASK_ID"

    # Post-claim: emit a reclaim signal when the task was already
    # Implementing by this same email. Two cases:
    #   RECLAIM_CRASH  — same host, prior PID anchor is PROVABLY dead
    #   RECLAIM_STATUS — anomaly fallback (anything else)
    # LOCK_RECLAIM: (cross-host) is emitted separately by aitask_lock.sh
    # and forwarded above; we still emit one of the below for completeness —
    # task-workflow's dispatcher prefers LOCK_RECLAIM > CRASH > STATUS.
    if [[ "$prev_status" == "Implementing" && -n "$EMAIL" \
          && "$prev_assigned" == "$EMAIL" && "$forced_takeover" == false ]]; then
        local current_host liveness
        current_host=$(hostname 2>/dev/null || echo "unknown")
        liveness=$(lock_holder_liveness "$prior_pid" "$prior_starttime" \
                                        "${prior_starttime_kind:-proc}")
        # ONLY a provably dead same-host anchor is a crash. The other two
        # verdicts no longer reach this point on a same-host lock: aitask_lock.sh's
        # acquire gate refuses a live holder (LOCK_LIVE_HOLDER) and an
        # undecidable one (LOCK_UNVERIFIABLE_HOLDER) BEFORE anything is claimed
        # (t1466). What still lands on RECLAIM_STATUS here is the honest
        # remainder: a lock that never recorded an anchor at all (pre-anchor,
        # or a claim made outside tmux), a cross-host lock, this session's own
        # refreshed lock, or a task whose Implementing status outlived its lock
        # entirely.
        #
        # `forced_takeover` suppresses the whole block: the user has just
        # confirmed a --force past one of those refusals, and re-asking
        # "reclaim and continue?" immediately afterwards would prompt twice for
        # one decision. (Different-email forces never matched the
        # prev_assigned test above, so this changes nothing for them.)
        if [[ "$prior_lock_host" == "$current_host" && "$liveness" == "dead" ]]; then
            echo "RECLAIM_CRASH:${prior_locked_at}|${prior_lock_host}|${prior_pid}"
        else
            echo "RECLAIM_STATUS:${prev_status}|${prev_assigned}"
        fi
    fi

    # Post-claim: snapshot the working tree's dirty set as this task's
    # attribution baseline (t1263). It is the "proven negative" signal
    # aitask_change_surface.sh uses to tell OTHER work's dirty paths from this
    # task's -- without it, a consumer like the docs_updated gate sees the whole
    # dirty tree with no way to know whose it is.
    #
    # FRESH CLAIMS ONLY. A reclaim/resume must keep the original baseline, or
    # this session's own in-progress work would be re-baselined as "other work".
    #
    # Runs LAST and fully silenced: every stdout line above is part of this
    # script's parsed output contract, so the capture must not be able to add to
    # it. Best-effort (`|| true`) per shell_conventions.md -- a capture failure
    # must never fail a claim; it degrades to BASELINE:missing, which makes the
    # consumer escalate rather than misattribute. Measured at ~17ms on a large
    # repo, against a claim that already does a fetch, a commit and a push.
    if [[ "$prev_status" != "Implementing" ]]; then
        "$SCRIPT_DIR/aitask_change_surface.sh" capture "$TASK_ID" >/dev/null 2>&1 || true
    fi
}

main "$@"
