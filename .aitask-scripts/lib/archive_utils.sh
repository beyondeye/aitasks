#!/usr/bin/env bash
# archive_utils.sh - Numbered archive path computation and search/extract primitives
# Source this file from aitask scripts; do not execute directly.
#
# Numbering scheme (0-indexed):
#   bundle = task_id / 100
#   dir    = bundle / 10
#   path   = archived/_b{dir}/old{bundle}.tar.zst
#
# Examples:
#   Task 0..99   -> archived/_b0/old0.tar.zst
#   Task 100..199 -> archived/_b0/old1.tar.zst
#   Task 1000..1099 -> archived/_b1/old10.tar.zst

# --- Guard against double-sourcing ---
[[ -n "${_AIT_ARCHIVE_UTILS_LOADED:-}" ]] && return 0
_AIT_ARCHIVE_UTILS_LOADED=1

# Ensure terminal_compat.sh is loaded (for die/warn helpers)
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# Startup sources — contract: aidocs/framework/shell_conventions.md (source-on-startup); scanner: tests/lib/shell_startup_closure.py
# shellcheck source=terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"

# ============================================================================
# Path computation functions (pure arithmetic, no I/O)
# ============================================================================

# Compute which bundle (0-indexed) a task belongs to.
# Bundle N holds tasks N*100..(N*100+99).
# Args: $1=task_id (numeric)
# Output: bundle number (integer)
archive_bundle() {
    local task_id="$1"
    echo $(( task_id / 100 ))
}

# Compute which directory (0-indexed) a bundle belongs to.
# Directory D holds bundles D*10..(D*10+9), i.e., tasks D*1000..(D*1000+999).
# Args: $1=bundle (numeric)
# Output: directory number (integer)
archive_dir() {
    local bundle="$1"
    echo $(( bundle / 10 ))
}

# Compute the full archive path for a given task ID.
# Args: $1=task_id (numeric), $2=archived_dir (base path, e.g. "aitasks/archived")
# Output: path like "aitasks/archived/_b0/old1.tar.zst"
archive_path_for_id() {
    local task_id="$1"
    local archived_dir="$2"
    local bundle dir
    # Non-numeric ids (e.g. "t1183") cannot be bundled — return empty instead
    # of crashing on the arithmetic under set -u.
    [[ "$task_id" =~ ^[0-9]+$ ]] || return 0
    bundle=$(( task_id / 100 ))
    dir=$(( bundle / 10 ))
    echo "${archived_dir}/_b${dir}/old${bundle}.tar.zst"
}

# ============================================================================
# Format-aware archive helpers (auto-detect by extension)
# ============================================================================

_archive_list() {
    local archive="$1"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" 2>/dev/null | tar -tf -
    else
        tar -tzf "$archive" 2>/dev/null
    fi
}

_archive_extract_file() {
    local archive="$1" filename="$2"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" | tar -xf - -O "$filename"
    else
        tar -xzf "$archive" -O "$filename"
    fi
}

_archive_extract_all() {
    local archive="$1" target_dir="$2"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" | tar -xf - -C "$target_dir"
    else
        tar -xzf "$archive" -C "$target_dir"
    fi
}

_archive_create() {
    local archive="$1" source_dir="$2"
    tar -cf - -C "$source_dir" . | zstd -q -o "$archive"
}

_archive_verify() {
    local archive="$1"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" | tar -tf - > /dev/null
    else
        tar -tzf "$archive" > /dev/null 2>&1
    fi
}

# ============================================================================
# Temp directory management
# ============================================================================
#
# Every extraction lands in `ait-archive.<owner>.XXXXXX` under a base pinned
# when this file is first sourced in a shell. The TAG is what lets the owning
# shell find those dirs (t2023): resolve_task_file / resolve_plan_file are
# always called inside `$( )`, where anything _extract_from_archive sets --
# _AIT_ARCHIVE_TMPDIR included -- dies with the subshell, and bash runs no EXIT
# trap in a command substitution. The parent cannot learn a dir's NAME, but it
# knows its own tag, and _ait_archive_cleanup sweeps by it.
#
# The base is PINNED rather than read per extraction: a scoped
# `$(TMPDIR=/x resolve_task_file N)` or an export-and-restore around a resolve
# would otherwise create the dir somewhere the sweep never looks.
#
# The tag is `<pid>.<nonce>`, not the PID alone: a PID is unique only within
# one PID namespace, and sandboxed commands in separate namespaces that share a
# TMPDIR (and a uid, so -O passes too) can both be pid 1 -- one's exit sweep
# then deleted the other's live extraction. The nonce makes the tag this
# shell's alone: SRANDOM (bash >= 5.1) is kernel-random; RANDOM and the
# microsecond clock only widen it on older shells.
#
# This state survives a re-source in the SAME shell (tests reset the
# double-source guard): re-pinning would orphan dirs already made, a new nonce
# would orphan them too, and resetting the stored caller handler would
# silently drop the caller's EXIT cleanup. `${BASHPID:-$$}` (as in
# stale_lock.sh) re-initializes it in a new shell; on bash 3.2 it is the
# process PID in every subshell, hence _ait_archive_may_sweep.
if [[ "${_AIT_ARCHIVE_OWNER_PID:-}" != "${BASHPID:-$$}" ]]; then
    _AIT_ARCHIVE_OWNER_PID="${BASHPID:-$$}"
    _ait_archive_now="${EPOCHREALTIME:-}"      # unset before bash 5.0; set -u safe
    _AIT_ARCHIVE_OWNER="${_AIT_ARCHIVE_OWNER_PID}.${SRANDOM:-$RANDOM}${RANDOM}${_ait_archive_now//[!0-9]/}"
    unset _ait_archive_now
    _AIT_ARCHIVE_TMPBASE="${TMPDIR:-/tmp}"
    [[ "$_AIT_ARCHIVE_TMPBASE" == /* ]] || _AIT_ARCHIVE_TMPBASE="$PWD/$_AIT_ARCHIVE_TMPBASE"
fi
: "${_AIT_ARCHIVE_CALLER_EXIT_TRAP:=}"   # written ONLY by _ait_archive_arm_exit_trap
_AIT_ARCHIVE_TMPDIR=""

# _ait_archive_may_sweep -- true iff this shell owns the tag. Always true where
# the trap fires on bash >= 4. On bash 3.2 (no BASHPID) a guard-reset re-source
# inside `( )` carries the PROCESS pid as its tag, so it must not sweep dirs
# the parent still holds; it removes only its own _AIT_ARCHIVE_TMPDIR.
_ait_archive_may_sweep() {
    if [[ -n "${BASHPID:-}" ]]; then
        [[ "$BASHPID" == "$_AIT_ARCHIVE_OWNER_PID" ]]
    else
        (( ${BASH_SUBSHELL:-0} == 0 ))
    fi
}

# _ait_archive_cleanup -- remove this shell's extraction dirs. ALWAYS returns 0
# and lets no failure escape: errexit is live inside an EXIT trap, where a
# failing command aborts the rest of the trap and turns `exit 0` into 1. An
# entry is removed only if it is a real directory (not a symlink), owned by us,
# and carries our tag -- never an untagged `tmp.*`, another owner's dir, or
# another user's.
_ait_archive_cleanup() {
    local base d bases=("$_AIT_ARCHIVE_TMPBASE")
    if [[ -n "$_AIT_ARCHIVE_TMPDIR" && -d "$_AIT_ARCHIVE_TMPDIR" ]]; then
        rm -rf "$_AIT_ARCHIVE_TMPDIR" 2>/dev/null || true
    fi
    _ait_archive_may_sweep || return 0
    # The pinned base, plus -- only when it differs -- the exit-time TMPDIR
    # for _extract_from_archive's fallback (the pinned base was deleted after
    # sourcing).
    [[ "${TMPDIR:-/tmp}" == "$_AIT_ARCHIVE_TMPBASE" ]] || bases+=("${TMPDIR:-/tmp}")
    for base in "${bases[@]}"; do
        for d in "$base"/ait-archive."$_AIT_ARCHIVE_OWNER".*; do
            if [[ -d "$d" && ! -L "$d" && -O "$d" ]]; then
                rm -rf -- "$d" 2>/dev/null || true
            fi
        done
    done
    return 0
}

# _ait_archive_exit_chain -- the EXIT handler installed when the sourcing
# shell already had one (t2023). Composing trap TEXT cannot work: an APPENDED
# command never runs after a handler that calls `exit` (ait_ledger_lock_exit_trap
# ends in one), and a PREPENDED one hands the caller our status instead of the
# dying one and trips ledger_block.sh's first-command detector. So this runs
# our cleanup first, then the caller's handler exactly as the UNWRAPPED
# composition would run it:
#   * `$?` is the status this function received -- the dying one, or whatever
#     a handler that a later composer prepended ahead of us returned;
#   * `trap -p EXIT` shows the CURRENT trap text with our token replaced by the
#     caller's handler. Not the caller's text alone: after a
#     txn_chain_exit_trap prepend that would tell the ledger detector it ran
#     first, and an `exit 42` would end as a silent 0.
# Re-arming EXIT inside the running handler does not re-run it, and
# `(exit N) && :` sets `$?` without tripping errexit (a failing non-final
# command of an && list is exempt). The caller's own `exit N` still decides.
_ait_archive_exit_chain() {
    local __ait_rc=$? __ait_cur __ait_now   # `__ait_rc=$?` MUST stay first
    _ait_archive_cleanup
    __ait_cur="$(trap -p EXIT)"
    __ait_cur="${__ait_cur#trap -- }"; __ait_cur="${__ait_cur% EXIT}"
    eval "__ait_now=$__ait_cur"             # unquote bash's own rendering
    case "$__ait_now" in
        *_ait_archive_exit_chain*)
            __ait_now="${__ait_now%%_ait_archive_exit_chain*}${_AIT_ARCHIVE_CALLER_EXIT_TRAP}${__ait_now#*_ait_archive_exit_chain}" ;;
        *)  __ait_now="$_AIT_ARCHIVE_CALLER_EXIT_TRAP" ;;
    esac
    trap -- "$__ait_now" EXIT
    (exit "$__ait_rc") && :
    eval "$_AIT_ARCHIVE_CALLER_EXIT_TRAP"
}

# _ait_archive_arm_exit_trap -- install the cleanup WITHOUT dropping an EXIT
# trap the sourcing script armed first (the bare `trap ... EXIT` this replaces
# silently clobbered e.g. a test's `trap 'rm -rf "$TMP"' EXIT`; t2023).
# Composes only in the process's top-level shell: inside `( )`, `trap -p`
# shows the PARENT's handler, which is not active there -- composing would run
# the parent's cleanup when the subshell exits, and trusting the display for
# idempotence would leave the subshell with no trap at all. Idempotent: a
# re-source finds our name and returns with the stored handler intact, and the
# substring match also keeps a re-source from storing a composition that
# already contains our chain (which would then eval itself).
_ait_archive_arm_exit_trap() {
    local cur
    if (( ${BASH_SUBSHELL:-0} > 0 )); then
        trap _ait_archive_cleanup EXIT
        return 0
    fi
    cur="$(trap -p EXIT)"
    case "$cur" in *_ait_archive_cleanup*|*_ait_archive_exit_chain*) return 0 ;; esac
    if [[ -z "$cur" ]]; then
        trap _ait_archive_cleanup EXIT
        return 0
    fi
    cur="${cur#trap -- }"; cur="${cur% EXIT}"
    eval "_AIT_ARCHIVE_CALLER_EXIT_TRAP=$cur"   # unquote bash's own rendering
    trap _ait_archive_exit_chain EXIT
}
_ait_archive_arm_exit_trap

# ============================================================================
# Single-archive primitives (matching task_utils.sh API)
# ============================================================================

# Search for a file matching a pattern inside an archive (tar.zst or tar.gz).
# Args: $1=archive_path, $2=grep_pattern (extended regex)
# Output: matching filename inside the tar (first match), or empty
_search_archive() {
    local archive="$1"
    local pattern="$2"
    [[ -f "$archive" ]] || return 0
    _archive_list "$archive" | grep -E "$pattern" | head -1
}

# Extract a file from an archive (tar.zst or tar.gz) to a temp location.
# Args: $1=archive_path, $2=filename_inside_tar
# Sets: _AIT_EXTRACT_RESULT to the path of the extracted temp file ("" with
#       status 1 when no temp dir could be made)
# Callable inside `$( )` (resolve_task_file always is). A direct call keeps
# _AIT_ARCHIVE_TMPDIR in the caller's shell and reuses that dir; a call inside
# `$( )` makes its own, which the owning shell's EXIT trap finds by its tag
# (see "Temp directory management").
_extract_from_archive() {
    local archive="$1"
    local filename="$2"
    if [[ -z "$_AIT_ARCHIVE_TMPDIR" ]]; then
        # The extraction-time TMPDIR is a fallback for a pinned base deleted
        # after sourcing only; the sweep also scans it for exactly that case.
        _AIT_ARCHIVE_TMPDIR=$(mktemp -d "${_AIT_ARCHIVE_TMPBASE}/ait-archive.${_AIT_ARCHIVE_OWNER}.XXXXXX" 2>/dev/null) \
            || _AIT_ARCHIVE_TMPDIR=$(mktemp -d "${TMPDIR:-/tmp}/ait-archive.${_AIT_ARCHIVE_OWNER}.XXXXXX" 2>/dev/null) \
            || { _AIT_ARCHIVE_TMPDIR=""; _AIT_EXTRACT_RESULT=""; return 1; }
    fi
    _AIT_EXTRACT_RESULT="$_AIT_ARCHIVE_TMPDIR/$(basename "$filename")"
    _archive_extract_file "$archive" "$filename" > "$_AIT_EXTRACT_RESULT" 2>/dev/null
}

# ============================================================================
# Multi-archive operations
# ============================================================================

# O(1) lookup: find the archive path for a given task ID.
# Returns the path if the archive file exists on disk, empty otherwise.
# Tries .tar.zst first, falls back to .tar.gz for backward compatibility.
# Args: $1=task_id (numeric parent ID), $2=archived_dir
# Output: archive path or empty string
_find_archive_for_task() {
    local task_id="$1"
    local archived_dir="$2"
    local zst_path gz_path
    zst_path=$(archive_path_for_id "$task_id" "$archived_dir")
    [[ -z "$zst_path" ]] && return 0
    if [[ -f "$zst_path" ]]; then
        echo "$zst_path"
        return
    fi
    gz_path="${zst_path%.tar.zst}.tar.gz"
    if [[ -f "$gz_path" ]]; then
        echo "$gz_path"
    fi
}

# Iterate all numbered archives searching for a pattern.
# Searches .tar.zst first, then .tar.gz (skipping .tar.gz if .tar.zst exists).
# Args: $1=archived_dir, $2=grep_pattern
# Output: "archive_path:matched_filename" for each match (one per line)
_search_all_archives() {
    local archived_dir="$1"
    local pattern="$2"
    local archive match
    for archive in "$archived_dir"/_b*/old*.tar.zst "$archived_dir"/_b*/old*.tar.gz; do
        [[ -f "$archive" ]] || continue
        # Skip .tar.gz if corresponding .tar.zst exists
        if [[ "$archive" == *.tar.gz ]]; then
            local zst_variant="${archive%.tar.gz}.tar.zst"
            [[ -f "$zst_variant" ]] && continue
        fi
        match=$(_search_archive "$archive" "$pattern")
        if [[ -n "$match" ]]; then
            echo "${archive}:${match}"
        fi
    done
}

# Search numbered archive first, then fall back to legacy archives.
# Tries .tar.zst first at each location, then .tar.gz for backward compat.
# Args: $1=task_id (numeric parent ID), $2=archived_dir, $3=grep_pattern
# Output: "archive_path:matched_filename" or empty
_search_numbered_then_legacy() {
    local task_id="$1"
    local archived_dir="$2"
    local pattern="$3"

    # Try numbered archive first (O(1) lookup): .tar.zst then .tar.gz
    local zst_path gz_path match
    zst_path=$(archive_path_for_id "$task_id" "$archived_dir")
    if [[ -n "$zst_path" ]]; then
        if [[ -f "$zst_path" ]]; then
            match=$(_search_archive "$zst_path" "$pattern")
            if [[ -n "$match" ]]; then
                echo "${zst_path}:${match}"
                return
            fi
        fi
        gz_path="${zst_path%.tar.zst}.tar.gz"
        if [[ -f "$gz_path" ]]; then
            match=$(_search_archive "$gz_path" "$pattern")
            if [[ -n "$match" ]]; then
                echo "${gz_path}:${match}"
                return
            fi
        fi
    fi

    # Fall back to legacy archives: .tar.zst then .tar.gz
    local legacy
    for legacy in "$archived_dir/old.tar.zst" "$archived_dir/old.tar.gz"; do
        if [[ -f "$legacy" ]]; then
            match=$(_search_archive "$legacy" "$pattern")
            if [[ -n "$match" ]]; then
                echo "${legacy}:${match}"
                return
            fi
        fi
    done
}
