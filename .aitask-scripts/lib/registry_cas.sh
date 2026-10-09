#!/usr/bin/env bash
# registry_cas.sh - optimistic compare-and-swap rewrite of a shared file (t1928).
# Source this file from aitask scripts; do not execute directly.
#
# The model registries are read-modify-written by three writers that never
# coordinated: the OpenCode discovery refresh (aitask_opencode_models.sh) and
# the two counter writers (aitask_usage_update.sh, aitask_verified_update.sh).
# Each one rendered the new file from what it had read and then replaced the
# file, so a write landing in between was silently discarded — in EITHER order:
# a counter bump erased by the refresh, or the refresh's rows erased by a
# counter writer that had read the registry before the refresh swapped in.
#
# ait_cas_rewrite closes that by rendering from a byte SNAPSHOT and swapping only
# if the live file still matches the snapshot:
#
#   snapshot -> render(snapshot) -> stage beside dest -> compare -> rename
#                                                           \-> changed: retry
#
# Optimistic, not a lock, on purpose: the registry also changes under generic
# task-data pulls (`ait sync`, `pick_own --sync`, the counters' ff-only
# converge), which would never take a lock. The compare sees a change from ANY
# source. What it cannot close is the few milliseconds between its own final
# compare and the rename — a writer that swaps inside that instant is still
# overwritten. That residual is accepted (t1928); do not describe this as a
# mutex.
#
# Provides:
#   ait_cas_rewrite <dest> <max_attempts> <render_fn> [args...]
#       Calls `render_fn <snapshot> [args...]`, which must print the complete new
#       content of <dest> on stdout. <snapshot> is a private byte copy of <dest>,
#       or the empty string when <dest> does not exist. The render runs in the
#       CURRENT shell (stdout redirected), so globals it sets survive the call.
#       Returns:
#         0  swapped in
#         1  render or staging failed — <dest> untouched
#         2  <dest> changed on every attempt — nothing written
#       Sets AIT_CAS_ATTEMPTS to the number of attempts used. Prints nothing
#       itself: callers capture values via $( ) and have --silent modes.
#
# RENDER FUNCTIONS MUST `return`, NEVER `exit` / `die`. The snapshot lives in a
# private temp dir that is removed inline on every return path — an exit from
# inside the render skips that cleanup. Report a failure by returning non-zero
# (set a global first when the caller needs to know why). Renderers also must
# not rely on `set -e`; see the note at the top of atomic_write.sh.
#
# No EXIT trap, for the reason atomic_write.sh gives: the counter writers own
# theirs, and bash has only one.
#
# Test seam (mirrors AITASK_VERIFIED_UPDATE_BEFORE_PUSH_HOOK): when
# AIT_CAS_BEFORE_SWAP_HOOK names a script, it runs after the render and before
# the compare, with AIT_CAS_ATTEMPT and AIT_CAS_DEST exported. Its stdout goes to
# stderr so it can never land in the staged file. A non-zero hook exit fails the
# attempt like a render failure (return 1).

[[ -n "${_AIT_REGISTRY_CAS_LOADED:-}" ]] && return 0
_AIT_REGISTRY_CAS_LOADED=1

_AIT_REGISTRY_CAS_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/atomic_write.sh
source "$_AIT_REGISTRY_CAS_SELF/atomic_write.sh"

# Out-param read by callers, which shellcheck cannot see from this library.
# shellcheck disable=SC2034
AIT_CAS_ATTEMPTS=0

# Per-call state, read by _ait_cas_render (run in the current shell by
# ait_atomic_render, so plain globals are the interface).
_AIT_CAS_DEST=""
_AIT_CAS_SNAPSHOT=""
_AIT_CAS_ATTEMPT=0
_AIT_CAS_CHANGED=0

# _ait_cas_snapshot <dest> <snap_path> — copy <dest> to <snap_path> and print
# the path, or print nothing when <dest> does not exist. `cp` reads one inode
# start to finish, so a concurrent rename yields the old or the new file whole.
_ait_cas_snapshot() {
    if [[ -f "$1" ]]; then
        cp "$1" "$2" || return 1
        printf '%s\n' "$2"
    fi
    return 0
}

# _ait_cas_unchanged — is the live dest still byte-identical to the snapshot?
# An absent snapshot means "dest did not exist", so it must still not exist.
_ait_cas_unchanged() {
    if [[ -z "$_AIT_CAS_SNAPSHOT" ]]; then
        [[ ! -e "$_AIT_CAS_DEST" ]]
    else
        cmp -s "$_AIT_CAS_SNAPSHOT" "$_AIT_CAS_DEST"
    fi
}

_ait_cas_hook() {
    [[ -n "${AIT_CAS_BEFORE_SWAP_HOOK:-}" ]] || return 0
    AIT_CAS_ATTEMPT="$_AIT_CAS_ATTEMPT" AIT_CAS_DEST="$_AIT_CAS_DEST" \
        bash "$AIT_CAS_BEFORE_SWAP_HOOK" >&2
}

# _ait_cas_render <render_fn> [args...] — the renderer handed to
# ait_atomic_render. The compare is its LAST act, so the only gap left before
# the rename is ait_atomic_render's own empty-file check and `mv`.
_ait_cas_render() {
    _AIT_CAS_CHANGED=0
    local fn="$1"
    shift
    "$fn" "$_AIT_CAS_SNAPSHOT" "$@" || return 1
    _ait_cas_hook || return 1
    if ! _ait_cas_unchanged; then
        _AIT_CAS_CHANGED=1
        return 1
    fi
}

ait_cas_rewrite() {
    local dest="$1" max="$2"
    shift 2
    local snap_dir rc=2 attempt
    # shellcheck disable=SC2034  # out-param, see above
    AIT_CAS_ATTEMPTS=0
    snap_dir="$(mktemp -d "${TMPDIR:-/tmp}/ait_registry_cas.XXXXXX")" || return 1

    _AIT_CAS_DEST="$dest"
    for (( attempt = 1; attempt <= max; attempt++ )); do
        # shellcheck disable=SC2034  # out-param, see above
        AIT_CAS_ATTEMPTS=$attempt
        _AIT_CAS_ATTEMPT=$attempt
        if ! _AIT_CAS_SNAPSHOT="$(_ait_cas_snapshot "$dest" "$snap_dir/snapshot")"; then
            rc=1
            break
        fi
        if ait_atomic_render "$dest" _ait_cas_render "$@"; then
            rc=0
            break
        fi
        if [[ "$_AIT_CAS_CHANGED" != 1 ]]; then
            rc=1
            break
        fi
        rc=2
    done

    rm -rf "$snap_dir"
    _AIT_CAS_SNAPSHOT=""
    return "$rc"
}
