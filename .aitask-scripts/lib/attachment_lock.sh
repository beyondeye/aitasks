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
# Sourced by aitask_attach.sh; requires task_utils.sh + registry_lock.sh.

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
