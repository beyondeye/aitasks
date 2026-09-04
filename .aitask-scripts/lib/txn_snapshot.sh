#!/usr/bin/env bash
# txn_snapshot.sh - the shared transaction boundary for data-branch mutations
# (t1698). Promoted verbatim-in-behaviour from aitask_fold_mark.sh's private
# _fold_snap_* facility (t1668), which was built for exactly this and is now
# ONE implementation shared by `ait fold`, `ait attach` and `ait artifact`.
#
# It provides two halves of one contract:
#
#   PREFLIGHT  txn_require_clean -- refuse to start when a path the transaction
#              will `git add` already has uncommitted changes. Staging is
#              whole-path, so path-scoping a commit does NOT stop a dirty path's
#              pre-existing edit from being published under an `ait:` message.
#
#   ROLLBACK   txn_snap_add / txn_snap_restore -- capture each path's
#              pre-mutation BYTES and its full `ls-files --stage` index entry,
#              and put both back on abort. Deliberately NOT a HEAD restore: HEAD
#              is what DESTROYS a pre-existing dirty edit, and a transaction's
#              own caller may legitimately have staged one.
#
# INVARIANT: a transaction either commits completely, or restores its own paths
# to their pre-transaction bytes and index entries.
#
# ─── THE VERDICT IS DERIVED, NEVER PLUMBED ───────────────────────────────────
#
# txn_rollback_failed returns 0 on purpose -- a failure restoring path 3 must
# not skip paths 4 and 5. That makes every caller of the shape
#
#     some_restore_step || rc=1        # WRONG: the `||` never fires
#
# a silent no-op, because the recorder it calls SUCCEEDED. Measured with the
# prune loop's exact shape: verdict rc=0 with one failure recorded. So every
# verdict here comes from txn_rollback_ok (or, inside txn_snap_restore, from the
# DELTA in the recorded set across the call). One derivation point, not N
# remembered `rc=1` assignments: a restore action added later cannot manufacture
# a false clean verdict by forgetting to propagate, because RECORDING IS THE
# PROPAGATION.
#
# ─── PATHS ARE DATA-ROOT-RELATIVE ────────────────────────────────────────────
#
# Every <relpath> below is relative to the DATA ROOT (the task_git contract),
# not to the process CWD. In branch mode only `aitasks/` and `aiplans/` are
# symlinked into the checkout (lib/data_symlinks.sh: AIT_DATA_LINKS), so
# `attachments/…` and `artifacts/…` do NOT resolve from the repo root. Git
# commands take the relpath; filesystem operations go through _txn_fs_path.
#
# Source this file; do not execute. Requires task_utils.sh (task_git,
# _ait_detect_data_worktree) and terminal_compat.sh (die/warn) to have been
# sourced by the caller.

[[ -n "${_AIT_TXN_SNAPSHOT_LOADED:-}" ]] && return 0
_AIT_TXN_SNAPSHOT_LOADED=1

_TXN_SNAP_DIR=""
_TXN_SNAP_PATHS=()               # index i -> relpath; i.blob / i.idx hold its state
_TXN_ACTIVE=false
_TXN_LABEL="transaction"
_TXN_ROLLBACK_HOOK=""            # verb-specific extra restore (blobs)
_TXN_RESTORE_FAILED=()           # every un-restored item, both halves
_TXN_SNAP_RESTORE_INCOMPLETE=false   # snapshot half specifically (drives cleanup)
declare -A _TXN_CLEAN_CHECKED=()
declare -A _TXN_SNAPSHOTTED=()

# _txn_fs_path <relpath> -- the on-disk path for a data-root-relative path.
_txn_fs_path() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" == "." ]]; then
        printf '%s' "$1"
    else
        printf '%s/%s' "$_AIT_DATA_WORKTREE" "$1"
    fi
}

# txn_rollback_failed <description> -- the ONLY way any restore action reports
# failure. Hooks call it instead of `|| true`; txn_snap_restore uses it too.
# ALWAYS returns 0: recording a failure must never abort the rest of the restore.
txn_rollback_failed() { _TXN_RESTORE_FAILED+=( "$1" ); return 0; }

# txn_rollback_ok -- the ONE verdict, DERIVED from what was recorded.
txn_rollback_ok() { (( ${#_TXN_RESTORE_FAILED[@]} == 0 )); }

# txn_snap_init -- start a fresh snapshot registry.
txn_snap_init() {
    _TXN_SNAP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_txn_snap_XXXXXX")" \
        || die "txn: could not create the snapshot directory"
    _TXN_SNAP_PATHS=()
    _TXN_RESTORE_FAILED=()
    _TXN_SNAP_RESTORE_INCOMPLETE=false
    _TXN_CLEAN_CHECKED=()
    _TXN_SNAPSHOTTED=()
}

# txn_require_clean <label> <relpath> -- refuse to start when <relpath> already
# has uncommitted changes. `git status --porcelain` covers all three shapes that
# a `git add` would sweep into the commit (unstaged modification, staged
# modification, untracked-but-present) and is empty for a path that does not
# exist yet -- the transaction-created case, which is clean by definition.
#
# Deduped independently of txn_snap_add: a SINGLE `seen` set is unsound, because
# whichever helper marked the path first would make the other skip -- leaving
# either nothing to restore or a dirty path committed.
#
# Deliberately NOT a stash-and-reapply: reapplying hunks around a commit can
# conflict, and stashing in a shared worktree is the very hazard this removes.
txn_require_clean() {
    local label="$1" p="$2" st
    [[ -n "${_TXN_CLEAN_CHECKED[$p]:-}" ]] && return 0
    _TXN_CLEAN_CHECKED["$p"]=1
    # `|| die`: a failed status read must not be misread as clean. errexit is
    # suppressed inside every caller (with_attach_lock), so the check is
    # explicit or it does not happen.
    st="$(task_git status --porcelain -- "$p")" \
        || die "${label}: could not read the git status of ${p} — refusing to start a transaction whose paths cannot be verified"
    [[ -z "$st" ]] && return 0
    die "${label}: ${p} has uncommitted changes — this operation stages that whole path, so its commit would absorb your edit. Commit it (./ait git commit -- ${p}) or revert it, then re-run."
}

# txn_snap_add <relpath> -- record one path's pre-mutation state. Absence is
# represented explicitly (no .blob file) so restore can DELETE a path the
# transaction created.
#
# A second call after the path was mutated is a NO-OP, so restore always yields
# the PRE-transaction bytes: restore replays in index order, and without the
# dedup a later snapshot would silently win.
txn_snap_add() {
    local p="$1" fs i
    [[ -n "$_TXN_SNAP_DIR" ]] || die "internal: txn_snap_add before txn_snap_init"
    [[ -n "${_TXN_SNAPSHOTTED[$p]:-}" ]] && return 0
    i="${#_TXN_SNAP_PATHS[@]}"
    fs="$(_txn_fs_path "$p")"
    if [[ -f "$fs" ]]; then
        cp -- "$fs" "$_TXN_SNAP_DIR/$i.blob" || die "txn: could not snapshot $p"
    fi
    # Empty when the path is not in the index; otherwise ONE line per index
    # entry ("<mode> <sha> <stage>\t<path>") -- THREE of them for a path in an
    # unresolved merge. Captured verbatim so update-index --index-info can
    # replay every stage; parsing a single mode/sha out of this and writing a
    # stage-0 entry would silently resolve the user's conflict.
    #
    # FAIL CLOSED on a read failure. `ls-files` exits 0 with empty output for a
    # path that is simply not in the index, so a NON-ZERO exit can only mean the
    # index could not be read -- and swallowing that would record "absent",
    # which on rollback makes --force-remove DELETE the caller's real index
    # entry instead of restoring it. Dying here is safe precisely because it is
    # still before the first mutation: there is nothing yet to roll back.
    task_git ls-files --stage -- "$p" > "$_TXN_SNAP_DIR/$i.idx" 2>/dev/null \
        || die "txn: could not read the index entry for $p — refusing to start a transaction that could not be rolled back"
    _TXN_SNAP_PATHS[i]="$p"
    _TXN_SNAPSHOTTED["$p"]=1
}

# txn_snap_restore -- put every snapshotted path back, index and worktree.
#
# The index half always REMOVES the current entry first (--force-remove drops
# every stage of a path, conflicted or not) and then replays the captured lines.
# That is what makes an unmerged path round-trip: all its stages come back
# exactly as they were, and a path that had no entry at all stays out.
#
# EVERY path is attempted -- a failure on one must not skip the rest -- and the
# status is DERIVED from the delta in _TXN_RESTORE_FAILED, never from a parallel
# rc variable (see the header).
txn_snap_restore() {
    local i p fs before=${#_TXN_RESTORE_FAILED[@]}
    (( ${#_TXN_SNAP_PATHS[@]} )) || return 0
    for i in "${!_TXN_SNAP_PATHS[@]}"; do
        p="${_TXN_SNAP_PATHS[$i]}"
        fs="$(_txn_fs_path "$p")"
        if [[ -f "$_TXN_SNAP_DIR/$i.blob" ]]; then
            cp -- "$_TXN_SNAP_DIR/$i.blob" "$fs" 2>/dev/null \
                || txn_rollback_failed "snapshot: $p (bytes not restored)"
        else
            rm -f -- "$fs" 2>/dev/null \
                || txn_rollback_failed "snapshot: $p (created by this transaction, not deleted)"
        fi
        # Counted, not `|| true`: --force-remove succeeds for a path that is not
        # in the index, so a real failure means an unwritable index -- and then
        # a stale entry survives that the .idx replay does not overwrite when
        # the snapshot recorded no entry at all.
        task_git update-index --force-remove -- "$p" >/dev/null 2>&1 \
            || txn_rollback_failed "snapshot: $p (index entry not cleared)"
        if [[ -s "$_TXN_SNAP_DIR/$i.idx" ]]; then
            task_git update-index --index-info < "$_TXN_SNAP_DIR/$i.idx" >/dev/null 2>&1 \
                || txn_rollback_failed "snapshot: $p (index entry not restored)"
        fi
    done
    task_git update-index -q --refresh >/dev/null 2>&1 || true
    (( ${#_TXN_RESTORE_FAILED[@]} == before )) && return 0
    _TXN_SNAP_RESTORE_INCOMPLETE=true
    return 1
}

# txn_snap_cleanup -- drop the snapshot directory, UNLESS the snapshot half of a
# restore failed. It is then the only surviving copy of the pre-transaction
# bytes, and deleting it would destroy the user's data at exactly the moment
# they need it. A hook-only failure has nothing in here to recover from, so it
# does not preserve the directory -- pointing someone at an irrelevant path is
# its own kind of dishonesty.
txn_snap_cleanup() {
    [[ "$_TXN_SNAP_RESTORE_INCOMPLETE" == true ]] && return 0
    if [[ -n "$_TXN_SNAP_DIR" && -d "$_TXN_SNAP_DIR" ]]; then
        rm -rf "$_TXN_SNAP_DIR"
    fi
    _TXN_SNAP_DIR=""
}

# txn_chain_exit_trap <handler> -- PREPEND <handler> to the current EXIT trap.
#
# Load-bearing, not stylistic. registry_lock_acquire installs
# `trap "registry_lock_release '<dir>'" EXIT`, OVERWRITING whatever the caller
# had, and registry_lock_release clears EXIT outright. So a rollback trap
# installed before with_attach_lock is destroyed by the acquire, and a bare
# `trap ... EXIT` inside the callback would LEAK THE GLOBAL ATTACH LOCK.
# Chaining puts the rollback first (it runs while the lock is still held) and
# the release second.
txn_chain_exit_trap() {
    local cur
    cur="$(trap -p EXIT)"; cur="${cur#trap -- }"; cur="${cur% EXIT}"
    eval "trap '$1; '$cur EXIT"
}

# _txn_exit_trap -- the EXIT handler installed by txn_begin. `die` calls `exit`,
# so there is no "every abort path" to instrument by hand: this trap IS every
# abort path.
#
# It captures $? as its FIRST command and never calls exit, so the script's own
# status survives it. It is first in the chain, so it destroys no status a later
# handler needs (registry_lock_release does not read $?).
# txn_rollback_report <ok:0|1> <context> -- the ONE place a rollback's outcome
# is worded, so the EXIT trap, the verbs' explicit failure arms and `ait fold`
# cannot drift into claiming different things about the same event.
txn_rollback_report() {
    local ok="$1" ctx="$2"
    if (( ok == 1 )); then
        warn "${ctx} — rolled back every mutation; nothing was committed"
        return 0
    fi
    {
        echo -e "${RED:-}Error: ${ctx} and the rollback did NOT fully restore:${NC:-}"
        printf '  - %s\n' "${_TXN_RESTORE_FAILED[@]}"
        echo "Nothing was committed, but the items above are left mid-transaction and need manual repair."
        [[ "$_TXN_SNAP_RESTORE_INCOMPLETE" == true ]] && \
            echo "Their pre-transaction contents are preserved in ${_TXN_SNAP_DIR} (<i>.blob = bytes, <i>.idx = index entry); remove that directory once repaired."
    } >&2
}

# txn_abort <message> -- the ONE abort helper for a verb's EXPLICIT failure arms
# (a commit that returned non-zero, a guard that refused). Rolls back, dies with
# <message> when the rollback was complete, and otherwise prints the itemized
# report first and marks the message so a caller reading only the `Error:` line
# still learns the tree was not fully restored.
#
# Every OTHER abort path is the EXIT trap's: `die` calls `exit`, so there is no
# list of call sites to keep in sync.
txn_abort() {
    local msg="$1"
    if txn_rollback; then
        die "$msg"
    fi
    txn_rollback_report 0 "${_TXN_LABEL}: aborted"
    die "$msg — INCOMPLETE ROLLBACK, see the report above"
}

_txn_exit_trap() {
    local rc=$?
    if [[ "$_TXN_ACTIVE" == true ]]; then
        local ok=1
        txn_rollback || ok=0
        txn_rollback_report "$ok" "${_TXN_LABEL}: aborted before the commit (exit ${rc})"
    fi
    txn_snap_cleanup
    return 0
}

# txn_begin <label> -- open a transaction: fresh snapshot registry, EXIT-trap
# rollback armed. Call it as the FIRST statement of a with_attach_lock callback,
# so it chains over the lock-release handler the acquire just installed.
txn_begin() {
    _TXN_LABEL="$1"
    _TXN_ROLLBACK_HOOK=""
    txn_snap_init
    txn_chain_exit_trap '_txn_exit_trap'
    _TXN_ACTIVE=true
}

# txn_on_rollback <fn> -- register the verb's blob-specific extra restore. Blob
# paths are content-addressed, so they keep HEAD restore / backend delete rather
# than being snapshotted (a snapshot would copy up to 25 MB per blob, and gc
# sweeps many). The hook reports failures with txn_rollback_failed, never
# `|| true`, and reads FILE-SCOPE globals -- never the dying frame's locals.
txn_on_rollback() { _TXN_ROLLBACK_HOOK="$1"; }

# txn_rollback -- undo the whole transaction. Idempotent: it disarms first, so
# the EXIT trap does not repeat what an explicit commit-failure arm already did.
# Returns non-zero if EITHER half recorded a failure.
txn_rollback() {
    _TXN_ACTIVE=false
    txn_snap_restore || true                                  # already recorded
    [[ -z "$_TXN_ROLLBACK_HOOK" ]] || "$_TXN_ROLLBACK_HOOK" || true
    txn_snap_cleanup
    txn_rollback_ok
}

# txn_end -- terminal success: disarm and drop the snapshot directory.
txn_end() {
    _TXN_ACTIVE=false
    txn_snap_cleanup
}
