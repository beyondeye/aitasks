#!/usr/bin/env bash
# registry_lock.sh - portable, fail-safe mutex for the per-user project registry.
# Source this file from aitask scripts; do not execute directly.
#
# The project registry (~/.config/aitasks/projects.yaml) is mutated by a
# whole-file read-modify-write in aitask_projects.sh. Those mutations fire
# concurrently — `ait projects add` runs silently on every tmux session bootstrap
# (lib/tmux_bootstrap.sh), so a restart burst launches many writers at once.
# Without serialization the last writer clobbers the others with its stale
# snapshot, silently dropping project_group / last_opened fields (t1073).
#
# This mutex serializes those critical sections. It is a `mkdir`-based lock
# (mkdir is atomic on POSIX; no `flock`, which is absent by default on macOS/BSD).
#
# Provides:
#   registry_lock_acquire <lock_dir> [timeout_secs=10]  -> 0 held / 1 busy
#   registry_lock_release <lock_dir>                    -> always 0
#
# Design invariants (do NOT relax — see aidocs / t1073 plan):
#   1. Never proceed unlocked. On timeout (a live holder we could not displace)
#      acquire returns 1 and writes nothing — the caller must fail/skip, never
#      write without the lock.
#   2. Owner-token release. Each acquisition writes a unique token; release
#      removes the lock ONLY when the on-disk token still matches ours. If our
#      lock was stolen (we were presumed dead), we never delete the new owner's.
#   3. Steal only a provably-dead holder, atomically. A held lock is displaced
#      ONLY when its recorded PID is dead (`kill -0` fails) — never by age. The
#      steal renames-then-removes so two stealers cannot both evict a live lock.

[[ -n "${_AIT_REGISTRY_LOCK_LOADED:-}" ]] && return 0
_AIT_REGISTRY_LOCK_LOADED=1

# One active lock per process. Set on acquire, cleared on release.
_registry_lock_dir=""
_registry_lock_token=""

# registry_lock_acquire <lock_dir> [timeout_secs]
# Returns 0 with the lock held, or 1 if a live holder kept it past the timeout.
registry_lock_acquire() {
    local dir="$1"
    local timeout="${2:-10}"
    local token deadline
    token="$$-${RANDOM}-${RANDOM}-$(date +%s)"   # unique per acquisition
    deadline=$(( $(date +%s) + timeout ))

    while ! mkdir "$dir" 2>/dev/null; do
        local holder
        holder=$(cat "$dir/pid" 2>/dev/null || echo "")
        # Steal ONLY a provably-dead holder, atomically. A missing/empty pid means
        # a holder that just won mkdir but has not written its pid yet — treat as
        # live and wait (never steal). Renaming first means only one stealer wins
        # the displacement; a live lock is never double-evicted.
        if [[ -n "$holder" ]] && ! kill -0 "$holder" 2>/dev/null; then
            local dead="$dir.dead.$$.$RANDOM"
            mv "$dir" "$dead" 2>/dev/null && rm -rf "$dead"
            continue
        fi
        if (( $(date +%s) >= deadline )); then
            return 1   # live holder, timed out → FAIL SAFELY (never write unlocked)
        fi
        sleep 0.05
    done

    printf '%s\n' "$$" > "$dir/pid"
    printf '%s\n' "$token" > "$dir/owner"
    _registry_lock_dir="$dir"
    _registry_lock_token="$token"
    # shellcheck disable=SC2064  # expand _registry_lock_dir now, on purpose
    trap "registry_lock_release '$dir'" EXIT
    return 0
}

# registry_lock_release <lock_dir>
# Removes the lock dir ONLY if this process still owns it (token match).
registry_lock_release() {
    local dir="$1"
    [[ -n "$_registry_lock_dir" && "$dir" == "$_registry_lock_dir" ]] || return 0
    local on_disk
    on_disk=$(cat "$dir/owner" 2>/dev/null || echo "")
    if [[ "$on_disk" == "$_registry_lock_token" ]]; then
        rm -rf "$dir" 2>/dev/null || true
    fi
    # else: our lock was stolen while we were presumed dead — leave it intact.
    _registry_lock_dir=""
    _registry_lock_token=""
    trap - EXIT
    return 0
}
