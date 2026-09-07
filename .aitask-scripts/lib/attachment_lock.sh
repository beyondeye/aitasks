#!/usr/bin/env bash
# attachment_lock.sh - the single global attach-transaction mutex (t1030_2).
#
# `ait attach add`/`rm` wrap their ENTIRE body (mutate meta -> mutate frontmatter
# -> stage -> commit -> rollback) in one held lock so no intermediate state is
# ever observable and a rollback can never clobber a concurrent op's valid ref.
# Standalone metadata MUTATIONS (t1030_3 gc/fold) must take this same lock — a
# per-blob lock would not exclude an in-flight add/rm transaction. Only one lock
# is ever held at a time (registry_lock.sh tracks a single active lock per
# process), so there is never a nested acquire.
#
# t1076_1: this same lock also guards ARTIFACT-MANIFEST mutations
# (lib/artifact_manifest.py create/set-current/set-backend) — manifests share
# the blob store with attachments and gc's blocking set unions manifest
# references, so one lock serializes both ledgers against the sweep.
#
# Sourced by aitask_attach.sh; requires task_utils.sh + registry_lock.sh.
#
# ─── CALLBACK CONTRACT (t1675) ───────────────────────────────────────────────
#
# ERREXIT IS OFF INSIDE THE CALLBACK. with_attach_lock runs the body as
# `"$@" || rc=$?`, and bash disables errexit for the ENTIRE invocation whose
# status is tested. So inside a callback:
#
#   1. a failing command does NOT abort the callback -- execution continues;
#   2. the callback's return status is that of its LAST command, so a trailing
#      successful assignment overwrites the failure and the wrapper returns 0.
#
# THE RULE: every call that reports failure by RETURNING non-zero must carry an
# explicit `|| die "..."`. That includes captures (`x="$(mutator ...)" || die`)
# and reads whose empty output would be misread as a legitimate answer.
#
# Helpers that `die` internally are already safe -- `die` calls `exit`, which
# beats the suppression. The dangerous ones are the thin fronts that return the
# helper's status: attach_meta (attachment_meta.sh), artifact_manifest
# (artifact_manifest.sh), a direct lib/frontmatter_patch.py invocation, and
# artifact_backend_put / artifact_backend_delete.
#
# DO NOT TRY TO RESTORE ERREXIT -- all four routes were measured and all fail:
#
#   * `( set -e; "$@" )` in a subshell           -- still suppressed
#   * `set +e; set -e` toggled inside it         -- still suppressed
#   * `set -E` plus an ERR trap                  -- the ERR trap is suppressed too
#   * removing the `|| rc=$?` from this wrapper  -- aitask_fold_mark.sh calls
#     `with_attach_lock _fold_attach_txn || _fold_attach_rc=$?`, which
#     re-suppresses errexit through the WHOLE callback chain no matter what this
#     wrapper does, and it must test the status (see the comment there).
#
# Only a background subshell (`( set -e; "$@" ) & wait $!`) restores it, and that
# forks away the parent state _fold_attach_txn depends on (snapshot accumulation,
# EXIT-trap chaining) -- it would break the t1668 rollback contract.
#
# A "callback declared success" sentinel was considered and REJECTED: a callback
# that continues past a swallowed failure still reaches its own success
# declaration, so the sentinel catches nothing the return status does not already
# report.
#
# ENFORCEMENT: tests/test_attach_lock_callback_contract.sh statically checks
# every with_attach_lock callback (and the same-file helpers it calls) for this
# rule, and pins the runtime behaviour with fault injection.
#
# THE OTHER HALF -- lib/txn_snapshot.sh (t1698). This contract stops a failure
# being reported as SUCCESS; it says nothing about what the failed callback left
# on disk. That is now owned by the shared transaction boundary, which every
# `ait attach` / `ait artifact` callback opens with `txn_begin`:
#
#   * a fail-closed PREFLIGHT (txn_require_clean) refuses to start when a
#     non-blob path the transaction would stage is already dirty -- `git add` is
#     whole-path, so the commit would otherwise absorb the user's in-flight edit;
#   * a snapshot-backed ROLLBACK restores pre-transaction BYTES AND INDEX
#     ENTRIES (never HEAD, which is what destroyed a pre-existing dirty edit),
#     fired from the EXIT trap so it covers every abort path rather than only
#     the commit-failure branch.
#
# The two compose deliberately: `die` still exits, and the trap it fires now
# leaves the tree as it found it. Invariant: a transaction either commits
# completely, or restores its own paths to their pre-transaction state -- and
# says so truthfully when it could not (txn_rollback_report).
#
# NOTE FOR A NEW CALLBACK: txn_begin must be the FIRST statement, so its EXIT
# trap CHAINS over the lock-release handler registry_lock_acquire just
# installed. A bare `trap ... EXIT` there would replace that handler and leak
# this lock on every aborted verb.

[[ -n "${_AIT_ATTACHMENT_LOCK_LOADED:-}" ]] && return 0
_AIT_ATTACHMENT_LOCK_LOADED=1

_AIT_ATTACHMENT_LOCK_DIR_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/registry_lock.sh
source "$_AIT_ATTACHMENT_LOCK_DIR_SELF/registry_lock.sh"

ATTACH_LOCK_TIMEOUT="${ATTACH_LOCK_TIMEOUT:-30}"

# attachment_lock_dir -> echo the global attach lock dir in the data worktree.
attachment_lock_dir() {
    _ait_detect_data_worktree
    printf '%s/attachments/.attach.lock' "$_AIT_DATA_WORKTREE"
}

# with_attach_lock <fn> [args...] -- acquire the global attach lock, run the
# transaction body, release. Fail-safe: die on busy (never proceed unlocked).
# registry_lock's EXIT trap releases the lock even if <fn> dies mid-transaction.
#
# The `|| rc=$?` below is what disables errexit for <fn> and everything it calls.
# It cannot be removed (a caller re-suppresses anyway) -- read the CALLBACK
# CONTRACT block at the top of this file before touching this function or
# writing a new callback.
with_attach_lock() {
    local dir; dir="$(attachment_lock_dir)"
    mkdir -p "$(dirname "$dir")"
    if ! registry_lock_acquire "$dir" "$ATTACH_LOCK_TIMEOUT"; then
        die "ait attach: another attach operation is in progress — retry (lock: $dir)"
    fi
    local rc=0
    "$@" || rc=$?
    registry_lock_release "$dir"
    return "$rc"
}
