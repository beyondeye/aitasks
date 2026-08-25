#!/usr/bin/env bash
# aitask_merge_task.sh - the Step 9 merge broker: one process owns the shared
# repo root for the whole merge critical section (t1560_1).
#
# Step 9's merge runs in the SHARED repo root, so concurrent tasks drive one
# HEAD, one index and one working tree. This script is the only sanctioned way
# to perform that merge: it holds lib/merge_lock.sh across checkout + merge, and
# RETAINS the reservation through conflict resolution, verification and cleanup,
# releasing only on an explicit `finish` / `abort`.
#
# EXIT STATUS IS DISJOINT FROM THE VERDICT (the `ait gates run` contract):
#   exit 0  a verdict was produced - INCLUDING BUSY and MERGE_CONFLICT
#   exit 1  infrastructure failure only (never a verdict)
#   exit 2  usage error
# Exactly one verdict line on STDOUT; progress (WAITING:...) goes to STDERR, so
# a caller can parse stdout as data. Run `--list-verdicts` for the full
# vocabulary - t1560_2's rendered Step 9 must define a branch for every one.
#
# TEST-ONLY SEAMS are gated on a MARKER FILE, never on AITASKS_LOCK_DIR:
# stale_lock.sh documents AITASKS_LOCK_DIR as a DEPLOYMENT seam ("point it at an
# admin-created shared base") for multi-user shared checkouts - precisely where
# serialization matters most. An env var alone must never be able to disable the
# mutex. The seams are honoured only when <lock_base>/.ait_merge_test_seams
# exists; NEVER create that file in a real lock base.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/merge_lock.sh
source "$SCRIPT_DIR/lib/merge_lock.sh"

verdict()  { printf '%s\n' "$*"; }            # stdout: the data channel
progress() { printf '%s\n' "$*" >&2; }        # stderr: human progress
infra()    { warn "aitask_merge_task: $*"; exit 1; }
usage_err(){ warn "aitask_merge_task: $*"; exit 2; }

BRANCH_RE='^[A-Za-z0-9._/-]+$'

# --- test-only seams -------------------------------------------------------
_test_seams_enabled() {
    local base
    base="$(dirname "$(merge_lock_dir)")" || return 1
    [[ -f "$base/.ait_merge_test_seams" ]]
}
_seam_lock_disabled() {
    [[ "${AIT_MERGE_LOCK_DISABLED:-}" == "1" ]] || return 1
    _test_seams_enabled || return 1
    warn "aitask_merge_task: TEST SEAM ACTIVE - mutex acquisition skipped"
    return 0
}
_seam_run_hook() {
    [[ -n "${AIT_MERGE_BROKER_HOOK:-}" ]] || return 0
    _test_seams_enabled || return 0
    warn "aitask_merge_task: TEST SEAM ACTIVE - running broker hook"
    eval "$AIT_MERGE_BROKER_HOOK" || true
}
# force-release rendezvous points, so the two windows that must be proven
# atomic can be driven deterministically instead of with a sleep:
#   PREGUARD  between Read 1 and the guard acquisition (case 12)
#   INGUARD   inside the guarded section, before the repair (case 13)
_seam_force_hook() {
    local var="$1" cmd
    cmd="$(eval "printf '%s' \"\${$var:-}\"")"
    [[ -n "$cmd" ]] || return 0
    _test_seams_enabled || return 0
    warn "aitask_merge_task: TEST SEAM ACTIVE - running $var"
    eval "$cmd" || true
}

# --- shared helpers --------------------------------------------------------
_anchor_or_refuse() {
    local pid
    pid="$(get_session_anchor_pid)"
    if [[ "$pid" == "$AIT_PID_ANCHOR_UNKNOWN" || "$pid" == "0" || -z "$pid" ]]; then
        return 1
    fi
    printf '%s' "$pid"
}

_merge_head_present() { [[ -f "$(git rev-parse --git-dir)/MERGE_HEAD" ]]; }
_unmerged_paths()     { git diff --name-only --diff-filter=U 2>/dev/null || true; }
_tree_dirty_tracked() { git status --porcelain -uno 2>/dev/null | grep -c . || true; }
_head_branch()        { git symbolic-ref --short HEAD 2>/dev/null || true; }

# _cleanup_lock_and_report <lock_dir> <verdict> — release then emit. Used on
# every PRE-MERGE refusal: the reservation is only retained once a merge was
# actually attempted.
# _release_and_verdict <lock_dir> <verdict> — release, then report.
#
# If the release FAILS (typically a leaked .gc guard; the merge lock deliberately
# opts out of markerless guard reclaim, since this file runs `git reset --hard`
# under the guard, so a recordless one here is never auto-
# stolen), the reservation is still held. Reporting the ordinary refusal
# verdict would tell the caller the lock is NOT held, so it would call neither
# finish nor abort and the lock would wedge with no machine-readable state.
# Report RETAINED:<original_verdict> instead - the caller learns both that the
# lock is held and what the underlying situation was.
_release_and_verdict() {
    local d="$1"; shift
    if merge_lock_release "$d"; then
        verdict "$@"
    else
        warn "merge lock '$d' could not be released - the reservation is STILL HELD"
        warn "recovery: aitask_merge_task.sh status, then force-release (rmdir '${d}.gc'/h.* '${d}.gc' first if a guard leaked)"
        verdict "RETAINED:$*"
    fi
    exit 0
}

# ============================ begin ========================================
cmd_begin() {
    local task_id="${1:-}" out_branch="${2:-}" task_branch="${3:-}"
    shift 3 || usage_err "begin needs <task_id> <output_branch> <task_branch>"
    local wait_secs=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --wait-secs) wait_secs="${2:-0}"; shift 2 ;;
            *) usage_err "unknown begin flag: $1" ;;
        esac
    done
    [[ -n "$task_id" && -n "$out_branch" && -n "$task_branch" ]] ||
        usage_err "begin needs <task_id> <output_branch> <task_branch>"
    [[ "$wait_secs" =~ ^[0-9]+$ ]] || usage_err "--wait-secs must be an integer"

    # User-authored refs never reach a command line as literals.
    local b
    for b in "$out_branch" "$task_branch"; do
        if ! [[ "$b" =~ $BRANCH_RE ]] || ! git check-ref-format --branch "$b" >/dev/null 2>&1; then
            verdict "UNSAFE_OUTPUT_BRANCH:$b"; exit 0
        fi
    done

    # The release capability must exist at ACQUIRE time, or we hand out a
    # reservation whose owner can never be proven.
    _anchor_or_refuse >/dev/null || { verdict "NO_SESSION_ANCHOR"; exit 0; }

    local dir waited=0
    dir="$(merge_lock_dir)" || infra "could not resolve the merge lock dir"

    if _seam_lock_disabled; then
        :
    else
        local slice=2 start holder
        start=$(date +%s)
        if ! merge_lock_acquire "$task_id" "$out_branch" "$task_branch" 0 "merge lock"; then
            while :; do
                waited=$(( $(date +%s) - start ))
                [[ "$waited" -ge "$wait_secs" ]] && break
                holder="$(merge_lock_read "$dir" task_id)"
                [[ -n "$holder" ]] || holder="unknown"
                progress "WAITING:$holder:$waited"
                if merge_lock_acquire "$task_id" "$out_branch" "$task_branch" "$slice" "merge lock"; then
                    break
                fi
            done
            waited=$(( $(date +%s) - start ))
            if [[ -z "$(merge_lock_read "$dir" task_id)" ]] ||
               ! merge_lock_authorize "$dir" "$task_id" >/dev/null 2>&1; then
                holder="$(merge_lock_read "$dir" task_id)"
                [[ -n "$holder" ]] || holder="unknown"
                verdict "BUSY:$holder:$waited"; exit 0
            fi
        fi
    fi

    # ---- critical section, in order ----
    if _merge_head_present; then
        _release_and_verdict "$dir" "STALE_MERGE_RESIDUE"
    fi
    local dirty; dirty="$(_tree_dirty_tracked)"
    if [[ "$dirty" -gt 0 ]]; then
        _release_and_verdict "$dir" "DIRTY_TREE:$dirty"
    fi
    if ! git rev-parse --verify --quiet "refs/heads/$out_branch" >/dev/null; then
        _release_and_verdict "$dir" "PREFLIGHT_MISSING:$out_branch"
    fi
    # Foreign-worktree check: the repo root is itself listed, so reject ONLY
    # when the holding path differs from the tree we operate in.
    local here foreign
    here="$(git rev-parse --show-toplevel)"
    foreign="$(git worktree list --porcelain | awk -v br="refs/heads/$out_branch" '
        /^worktree /  { p=substr($0,10) }
        /^branch /    { if (substr($0,8)==br) print p }' | head -n1)"
    if [[ -n "$foreign" && "$foreign" != "$here" ]]; then
        _release_and_verdict "$dir" "PREFLIGHT_FOREIGN_WORKTREE:$foreign"
    fi

    # These are PRE-MERGE refusals, so they RELEASE - and must therefore not be
    # reported as MERGE_FAILED, whose contract is that the reservation is
    # RETAINED. A caller told MERGE_FAILED runs the held-lock recovery path
    # (abort / force-release) against a lock that is already free.
    local co_out co_rc=0
    co_out="$(git checkout "$out_branch" -- 2>&1)" || co_rc=$?
    if [[ "$co_rc" -ne 0 ]]; then
        _release_and_verdict "$dir" \
            "PREFLIGHT_CHECKOUT_FAILED:$(printf '%s' "$co_out" | tr '\n' ' ' | cut -c1-200)"
    fi
    local head_now; head_now="$(_head_branch)"
    if [[ "$head_now" != "$out_branch" ]]; then
        _release_and_verdict "$dir" "PREFLIGHT_HEAD_MISMATCH:$out_branch:${head_now:-DETACHED}"
    fi

    _seam_run_hook

    # From here the lock is RETAINED on every outcome - that retention is what
    # keeps a conflict-parked tree reserved.
    local merge_out merge_rc=0
    merge_out="$(git merge "$task_branch" 2>&1)" || merge_rc=$?
    if [[ "$merge_rc" -eq 0 ]]; then
        verdict "MERGE_OK:$(git rev-parse HEAD)"; exit 0
    fi
    local unmerged; unmerged="$(_unmerged_paths | paste -sd, - || true)"
    if [[ -n "$unmerged" ]]; then
        verdict "MERGE_CONFLICT:$unmerged"; exit 0
    fi
    verdict "MERGE_FAILED:$(printf '%s' "$merge_out" | tr '\n' ' ' | cut -c1-200)"
    exit 0
}

# ============================ finish =======================================
cmd_finish() {
    local task_id="${1:-}"
    [[ -n "$task_id" ]] || usage_err "finish needs <task_id>"
    local dir; dir="$(merge_lock_dir)" || infra "could not resolve the merge lock dir"
    [[ -e "$dir" ]] || { verdict "NOT_HELD"; exit 0; }
    local why
    if ! why="$(merge_lock_authorize "$dir" "$task_id")"; then
        verdict "$why"; exit 0
    fi
    if merge_lock_release "$dir"; then verdict "RELEASED"; else verdict "RETAINED:release_failed"; fi
    exit 0
}

# ============================ abort ========================================
cmd_abort() {
    local task_id="${1:-}"
    [[ -n "$task_id" ]] || usage_err "abort needs <task_id>"
    local dir; dir="$(merge_lock_dir)" || infra "could not resolve the merge lock dir"
    [[ -e "$dir" ]] || { verdict "NOT_HELD"; exit 0; }
    local why
    if ! why="$(merge_lock_authorize "$dir" "$task_id")"; then
        verdict "$why"; exit 0
    fi

    local out_branch; out_branch="$(merge_lock_read "$dir" output_branch)"
    # Branch on the OBSERVED state: `git merge` fails BEFORE creating MERGE_HEAD
    # for a whole class of errors, and `git merge --abort` on that state exits
    # non-zero - on a path whose only job is to release, that would strand the
    # reservation permanently.
    if _merge_head_present; then
        git merge --abort >/dev/null 2>&1 || true
        # Verify AFTER the action; never infer state from an exit status.
        if _merge_head_present || [[ "$(_tree_dirty_tracked)" -gt 0 ]] ||
           { [[ -n "$out_branch" ]] && [[ "$(_head_branch)" != "$out_branch" ]]; }; then
            verdict "ABORT_FAILED:merge --abort did not reach a clean state"; exit 0
        fi
        _release_and_verdict "$dir" "ABORTED"
    fi
    if [[ -n "$(_unmerged_paths)" ]]; then
        verdict "ABORT_UNSAFE:unmerged_index_no_merge_head:--reset-hard"; exit 0
    fi
    if [[ "$(_tree_dirty_tracked)" -gt 0 ]]; then
        verdict "ABORT_UNSAFE:dirty_tree:--reset-hard"; exit 0
    fi
    if [[ -z "$(_head_branch)" ]]; then
        verdict "ABORT_UNSAFE:detached_head:--reset-hard"; exit 0
    fi
    _release_and_verdict "$dir" "RELEASED_NO_MERGE"
}

# ============================ cleanup ======================================
cmd_cleanup() {
    local task_id="${1:-}" task_name="${2:-}"
    shift 2 2>/dev/null || usage_err "cleanup needs <task_id> <task_name>"
    local complete=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --task-complete) complete=1; shift ;;
            *) shift ;;                      # legacy positional path: ignored
        esac
    done
    [[ -n "$task_id" && -n "$task_name" ]] || usage_err "cleanup needs <task_id> <task_name>"

    local dir; dir="$(merge_lock_dir)" || infra "could not resolve the merge lock dir"
    [[ -e "$dir" ]] || { verdict "NOT_HELD"; exit 0; }
    local why
    if ! why="$(merge_lock_authorize "$dir" "$task_id")"; then
        verdict "$why"; exit 0
    fi
    # Completion is REQUIRED, not assumed: deleting aitask/<task_name> on a path
    # that leaves the task in-flight destroys the branch its resume must merge.
    if [[ "$complete" -ne 1 ]]; then
        verdict "CLEANUP_REQUIRES_COMPLETION"; exit 0
    fi
    local recorded; recorded="$(merge_lock_read "$dir" task_branch)"
    if [[ -n "$recorded" && "$recorded" != "aitask/$task_name" ]]; then
        verdict "TARGET_MISMATCH:$recorded"; exit 0
    fi

    # Delegate to the canonical classifier/teardown (t1548). It resolves the
    # worktree from its own git record, so a MOVED worktree is torn down rather
    # than silently missed - which is why no worktree path is accepted here.
    # It never runs `git worktree prune` and never uses `git branch -D`.
    local out rc=0
    out="$("$SCRIPT_DIR/aitask_task_worktree.sh" remove "$task_name" --strict 2>/dev/null)" || rc=$?
    local n; n="$(printf '%s' "$out" | grep -c . || true)"
    if [[ "$rc" -gt 1 || "$n" -ne 3 ]]; then
        # exit 2/3 print NOTHING to stdout: the cleanup did not run. Never
        # report that as success, and keep the reservation.
        verdict "CLEANED_PARTIAL:cleanup_did_not_run"; exit 0
    fi
    local last; last="$(printf '%s\n' "$out" | tail -n1)"
    if [[ "$rc" -eq 0 && "$last" == "CLEAN" ]]; then
        verdict "CLEANED"; exit 0
    fi
    local remains
    remains="$(printf '%s\n' "$out" | grep -E '^(WORKTREE_KEPT|BRANCH_KEPT)' | awk '{print $1"="$2}' | paste -sd, - || true)"
    [[ -n "$remains" ]] || remains="$last"
    verdict "CLEANED_PARTIAL:$remains"; exit 0
}

# ============================ status =======================================
cmd_status() {
    local dir; dir="$(merge_lock_dir)" || infra "could not resolve the merge lock dir"
    if [[ ! -e "$dir" ]]; then
        if [[ -e "${dir}.gc" ]]; then
            verdict "FREE_GUARD_PRESENT:${dir}.gc"
        else
            verdict "FREE"
        fi
        exit 0
    fi
    local holder pid live
    holder="$(merge_lock_read "$dir" task_id)"
    pid="$(merge_lock_read "$dir" pid)"; [[ -n "$pid" ]] || pid="-"
    live="$(merge_lock_liveness "$dir")"
    if [[ -z "$holder" ]]; then
        # Never matchable by finish and never auto-reclaimed: its own state.
        verdict "HOLDER_INCOMPLETE:$pid|$live"
    else
        verdict "HELD:$holder|$pid|$live|$(merge_lock_read "$dir" output_branch)|$(merge_lock_read "$dir" acquired_at)"
    fi
    [[ -e "${dir}.gc" ]] && progress "guard present: ${dir}.gc (if no reclaim is running: rmdir '${dir}.gc'/h.* '${dir}.gc')"
    exit 0
}

# ========================= force-release ===================================
_FR_VERDICT=""
_FR_READ1=""
_FR_REMEDY=""
_FR_EXPECT=""

# Snapshot of exactly the fields the dry-run prints.
_fr_snapshot() {
    local d="$1"
    printf '%s|%s|%s|%s|%s|%s' \
        "$(merge_lock_read "$d" task_id)" \
        "$(merge_lock_read "$d" pid)" \
        "$(merge_lock_read "$d" anchor_token)" \
        "$(merge_lock_read "$d" anchor_kind)" \
        "$(merge_lock_read "$d" acquired_at)" \
        "$(merge_lock_liveness "$d")"
}

# shellcheck disable=SC2329  # invoked indirectly via stale_lock_guard_critical
# _digest <string> — a short, opaque, shell-safe holder token. Hex only, so the
# documented --expect command needs no quoting decisions from the human.
_digest() {
    local out
    if command -v sha256sum >/dev/null 2>&1; then
        out="$(printf '%s' "$1" | sha256sum | cut -c1-16)"
    elif command -v shasum >/dev/null 2>&1; then
        out="$(printf '%s' "$1" | shasum -a 256 | cut -c1-16)"
    else
        out="$(printf '%s' "$1" | cksum | tr -cd '0-9')"
    fi
    printf '%s' "$out"
}

# shellcheck disable=SC2329  # invoked indirectly via stale_lock_guard_critical
_fr_delete() { _stale_lock_rm_verified "$1"; }

# Runs UNDER the .gc guard: revalidate -> repair -> verify -> delete. Nothing
# here may assume the dry-run's observation is still true.
# shellcheck disable=SC2329  # invoked indirectly via stale_lock_guarded_section
_fr_guarded() {
    local d="$1" read2 live holder
    _seam_force_hook AIT_MERGE_FORCE_HOOK_INGUARD
    if [[ ! -e "$d" ]]; then _FR_VERDICT="NOT_HELD"; return 0; fi
    read2="$(_fr_snapshot "$d")"
    holder="$(merge_lock_read "$d" task_id)"; [[ -n "$holder" ]] || holder="-"
    live="$(merge_lock_liveness "$d")"

    if [[ "$read2" != "$_FR_READ1" ]]; then
        _FR_VERDICT="HOLDER_CHANGED:$holder"; return 0
    fi
    if [[ -n "$_FR_EXPECT" && "$_FR_EXPECT" != "$(_digest "$read2")" ]]; then
        _FR_VERDICT="HOLDER_CHANGED:$holder"; return 0
    fi
    if [[ "$live" == "alive" ]]; then
        _FR_VERDICT="REFUSED_LIVE_HOLDER:$holder:$(merge_lock_read "$d" pid)"; return 0
    fi

    # Two distinct remedies; a mismatched flag is REFUSED, never attempted.
    if _merge_head_present; then
        if [[ "$_FR_REMEDY" != "--abort-merge" ]]; then
            _FR_VERDICT="RESIDUE_PRESENT:merge_head:--abort-merge"; return 0
        fi
        git merge --abort >/dev/null 2>&1 || true
        if _merge_head_present || [[ "$(_tree_dirty_tracked)" -gt 0 ]] || [[ -z "$(_head_branch)" ]]; then
            _FR_VERDICT="RECOVERY_FAILED:tree not clean after merge --abort"; return 0
        fi
    elif [[ -n "$(_unmerged_paths)" ]] || [[ "$(_tree_dirty_tracked)" -gt 0 ]]; then
        if [[ "$_FR_REMEDY" == "--abort-merge" ]]; then
            _FR_VERDICT="WRONG_REMEDY:no_merge_head"; return 0
        fi
        if [[ "$_FR_REMEDY" != "--reset-hard" ]]; then
            _FR_VERDICT="RESIDUE_PRESENT:unmerged_index_no_merge_head:--reset-hard"; return 0
        fi
        warn "force-release: discarding the following working-tree state:"
        git status --porcelain >&2 || true
        git reset --hard HEAD >/dev/null 2>&1 || true
        if [[ "$(_tree_dirty_tracked)" -gt 0 ]] || [[ -z "$(_head_branch)" ]]; then
            _FR_VERDICT="RECOVERY_FAILED:tree not clean after reset --hard"; return 0
        fi
    elif [[ "$_FR_REMEDY" == "--abort-merge" ]]; then
        _FR_VERDICT="WRONG_REMEDY:no_merge_head"; return 0
    fi

    # Destroy LAST, and masked: an interrupt between "lock removed" and "guard
    # released" is the one ordering that strands a guard over no lock.
    if stale_lock_guard_critical _fr_delete "$d"; then
        _FR_VERDICT="FORCE_RELEASED:$holder"
    else
        _FR_VERDICT="RECOVERY_FAILED:could not remove $d"
    fi
    return 0
}

cmd_force_release() {
    local yes=0
    _FR_REMEDY=""; _FR_EXPECT=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --abort-merge|--reset-hard) _FR_REMEDY="$1"; shift ;;
            --yes)    yes=1; shift ;;
            --expect) _FR_EXPECT="${2:-}"; shift 2 ;;
            *) usage_err "unknown force-release flag: $1" ;;
        esac
    done
    local dir; dir="$(merge_lock_dir)" || infra "could not resolve the merge lock dir"
    if [[ ! -e "$dir" ]]; then verdict "NOT_HELD"; exit 0; fi

    # Read 1: the inspected snapshot, taken BEFORE the guard - exactly what the
    # dry-run prints, and what the guarded re-read is compared against.
    _FR_READ1="$(_fr_snapshot "$dir")"

    if [[ "$yes" -ne 1 ]]; then
        # Destructive-step preflight: resolved target + blast radius, first.
        progress "force-release DRY RUN (nothing will be touched)"
        progress "  lock dir : $dir"
        progress "  holder   : $(merge_lock_read "$dir" task_id)"
        progress "  anchor   : pid=$(merge_lock_read "$dir" pid) liveness=$(merge_lock_liveness "$dir")"
        progress "  acquired : $(merge_lock_read "$dir" acquired_at)"
        if _merge_head_present; then
            progress "  residue  : MERGE_HEAD present -> remedy --abort-merge"
        elif [[ -n "$(_unmerged_paths)" ]] || [[ "$(_tree_dirty_tracked)" -gt 0 ]]; then
            progress "  residue  : unmerged index / dirty tree, no MERGE_HEAD -> remedy --reset-hard"
            git status --porcelain >&2 || true
        else
            progress "  residue  : none -> no remedy flag needed"
        fi
        progress "  If a leaked .gc guard blocks recovery: rmdir '${dir}.gc'/h.* '${dir}.gc' (never rm -rf)"
        local tok remedy_hint
        tok="$(_digest "$_FR_READ1")"
        if _merge_head_present; then remedy_hint=" --abort-merge"
        elif [[ -n "$(_unmerged_paths)" ]] || [[ "$(_tree_dirty_tracked)" -gt 0 ]]; then remedy_hint=" --reset-hard"
        else remedy_hint=""; fi
        progress "  holder token: $tok"
        progress "  To act on EXACTLY this holder, copy this line verbatim:"
        progress "    ./.aitask-scripts/aitask_merge_task.sh force-release${remedy_hint} --yes --expect $tok"
        verdict "DRY_RUN:$tok"
        exit 0
    fi

    _FR_VERDICT=""
    # Read 1 is taken above; anything that replaces the holder from here until
    # the guard is held must be caught by the guarded re-read, not acted on.
    _seam_force_hook AIT_MERGE_FORCE_HOOK_PREGUARD
    if ! stale_lock_guarded_section "$dir" _fr_guarded; then
        [[ -n "$_FR_VERDICT" ]] || { verdict "LOCK_UNAVAILABLE:guard_busy"; exit 0; }
    fi
    [[ -n "$_FR_VERDICT" ]] || _FR_VERDICT="LOCK_UNAVAILABLE:guard_busy"
    verdict "$_FR_VERDICT"
    exit 0
}

# ======================= verdict vocabulary ================================
# BEGIN_VERDICT_VOCABULARY  (t1560_2 parses this block - keep the markers)
_VERDICTS_BEGIN="MERGE_OK MERGE_CONFLICT MERGE_FAILED BUSY PREFLIGHT_MISSING UNSAFE_OUTPUT_BRANCH PREFLIGHT_FOREIGN_WORKTREE PREFLIGHT_CHECKOUT_FAILED PREFLIGHT_HEAD_MISMATCH DIRTY_TREE STALE_MERGE_RESIDUE NO_SESSION_ANCHOR LOCK_UNAVAILABLE RETAINED"
_VERDICTS_FINISH="RELEASED NOT_HELD NOT_HOLDER NOT_OWNER_SESSION RETAINED HOLDER_INCOMPLETE"
_VERDICTS_ABORT="ABORTED ABORT_FAILED ABORT_UNSAFE RELEASED_NO_MERGE NOT_HELD NOT_HOLDER NOT_OWNER_SESSION HOLDER_INCOMPLETE RETAINED"
_VERDICTS_CLEANUP="CLEANED CLEANED_PARTIAL CLEANUP_REQUIRES_COMPLETION TARGET_MISMATCH NOT_HELD NOT_HOLDER NOT_OWNER_SESSION HOLDER_INCOMPLETE"
_VERDICTS_STATUS="FREE FREE_GUARD_PRESENT HELD HOLDER_INCOMPLETE"
_VERDICTS_FORCE_RELEASE="DRY_RUN FORCE_RELEASED REFUSED_LIVE_HOLDER HOLDER_CHANGED RESIDUE_PRESENT WRONG_REMEDY RECOVERY_FAILED NOT_HELD LOCK_UNAVAILABLE"
# END_VERDICT_VOCABULARY
cmd_list_verdicts() {
    local v
    for v in begin finish abort cleanup status force-release; do
        case "$v" in
            begin)         printf 'begin: %s\n'         "$_VERDICTS_BEGIN" ;;
            finish)        printf 'finish: %s\n'        "$_VERDICTS_FINISH" ;;
            abort)         printf 'abort: %s\n'         "$_VERDICTS_ABORT" ;;
            cleanup)       printf 'cleanup: %s\n'       "$_VERDICTS_CLEANUP" ;;
            status)        printf 'status: %s\n'        "$_VERDICTS_STATUS" ;;
            force-release) printf 'force-release: %s\n' "$_VERDICTS_FORCE_RELEASE" ;;
        esac
    done
    exit 0
}

# ============================ dispatch =====================================
[[ $# -gt 0 ]] || usage_err "usage: aitask_merge_task.sh <begin|finish|abort|cleanup|status|force-release|--list-verdicts> ..."
cmd="$1"; shift
case "$cmd" in
    begin)           cmd_begin "$@" ;;
    finish)          cmd_finish "$@" ;;
    abort)           cmd_abort "$@" ;;
    cleanup)         cmd_cleanup "$@" ;;
    status)          cmd_status "$@" ;;
    force-release)   cmd_force_release "$@" ;;
    --list-verdicts) cmd_list_verdicts ;;
    *) usage_err "unknown verb: $cmd" ;;
esac
