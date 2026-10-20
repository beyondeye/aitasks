#!/usr/bin/env bash
# aitask_scratchpad_store.sh - Locked lifecycle helper for the per-task
# scratchpad notes store (t2073_1).
#
# The store lives at `${AITASK_SCRATCHPAD_DIR:-.aitask-scratchpad}/<task_id>/`
# — bare task id (no `t` prefix, mirroring `.aitask-shadow/`), repo-root-relative,
# git-ignored, never committed. It holds:
#
#   notes.md      - the scratchpad text, written only by `save` (atomic render)
#   .holder.lock  - created only by `open`; the scratchpad app holds an
#                   fcntl.flock on it (opened O_RDWR WITHOUT O_CREAT) so one task
#                   has at most one writing editor. The kernel releases the flock
#                   on any death, so there is no stale-holder state to recover.
#
# LIFECYCLE LOCK. open / save / prune are serialized by ONE per-task
# `lib/registry_lock.sh` mutex that lives OUTSIDE the store:
# `<root>/.locks/<task_id>.lockd`. No verb therefore has to create the store just
# to lock it (the shadow helper's lock lives inside its store dir and so mkdirs
# it — not copied here), and prune can delete the whole store while holding it.
#
#   open   - under the lock: refuse NO_TASK unless the task file is still active,
#            then create the store and `.holder.lock`.
#   save   - under the lock: refuse ARCHIVED unless the task file is still active
#            (checked even when the store dir survives), then ABSENT when the
#            store dir is gone. Never creates the store.
#   prune  - every check, the sweep and the rmdir run under the lock. Archival
#            moves the task file BEFORE it prunes, so an open/save racing it
#            either completes wholly before the move (and its store is pruned
#            after) or sees the moved file and refuses — no resurrection.
#            The one pre-lock exit is a missing ROOT: every lifecycle verb
#            creates `<root>/.locks` before locking, so with no root no critical
#            section can be in flight. It also keeps archival from creating
#            `.aitask-scratchpad/` in repos that never used a scratchpad.
#
# TIMEOUT. LOCK_TIMEOUT is a LOCK-WAIT budget only: registry_lock_acquire spends
# it on acquisition. The work a verb does once it holds the lock (render, rename,
# find/rmdir) and the stdin read `save` does before it have no deadline, so no
# verb's total duration is bounded by this value.
#
# ROOT. A root containing a `..` segment is refused (exit 2) by every verb before
# any filesystem access. `path` prints the store's identity key — the canonical
# absolute store dir, computed without creating anything and identical before and
# after the root and store exist (the scratchpad pane stamps it into
# `@aitask_scratchpad_store`; bare task ids collide across projects on one tmux
# server).
#
# `task_utils.sh` is deliberately NOT sourced: it pulls in lib/archive_utils.sh,
# which claims the process-wide EXIT trap at source time, and registry_lock's own
# EXIT trap would clobber it. Nothing here needs it.
#
# TEST SEAM. When AITASK_SCRATCHPAD_PAUSE_FIFO is set, `open` pauses after its
# task check and `save` after its existence check: the verb writes the point name
# to `<fifo>.reached`, then blocks reading one line from the fifo. Test-only.
#
# Callers: aitask_archive.sh (`prune`, best-effort) and the scratchpad app
# (`open`, `save`, `path`).
#
# Verbs:
#   open <task_id>   - Prints OPENED:<canonical store dir>/notes.md, or NO_TASK
#                      when the task file is not active.
#   save <task_id>   - Notes text on stdin (NUL bytes are not supported). Prints
#                      SAVED:<bytes>, SAVED:empty (empty input removes notes.md),
#                      ARCHIVED (task file no longer active) or ABSENT (store dir
#                      gone). Never creates the store.
#   path <task_id>   - Prints the canonical absolute store dir. Creates nothing.
#   prune <task_id>  - Deletes the task's store. Prints PRUNED:<task_id> or
#                      PRUNED:absent. Called at archival, best-effort.
#
# Exit codes:
#   0  success (including NO_TASK / ARCHIVED / ABSENT / PRUNED:absent)
#   2  usage error / malformed task id / `..` segment in the root
#   3  LOCK_BUSY   - another process holds the lifecycle lock; NOTHING was changed
#   4  ERROR       - the store could not be written or pruned

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/registry_lock.sh
source "$SCRIPT_DIR/lib/registry_lock.sh"
# shellcheck source=lib/atomic_write.sh
source "$SCRIPT_DIR/lib/atomic_write.sh"

SCRATCHPAD_DIR="${AITASK_SCRATCHPAD_DIR:-.aitask-scratchpad}"

# Lock-wait budget for every verb — see TIMEOUT in the header.
LOCK_TIMEOUT=5

# Populated by resolve_task_id / store_paths_for / capture_key.
TASK_ID=""
STORE_DIR=""
STORE_FILE=""
HOLDER_FILE=""
LOCKS_DIR=""
LOCK_DIR=""
STORE_KEY=""
SAVE_BUF=""

usage() {
    cat >&2 <<'EOF'
Usage: aitask_scratchpad_store.sh open <task_id>
       aitask_scratchpad_store.sh save <task_id>    (notes text on stdin)
       aitask_scratchpad_store.sh path <task_id>
       aitask_scratchpad_store.sh prune <task_id>
EOF
    exit 2
}

# Usage-class refusal with a specific reason. Exit 2, never `die` (which is 1).
err_usage() {
    printf 'Error: %s\n' "$1" >&2
    exit 2
}

# Validate and normalize the task id, matching aitask_shadow_rejected.sh.
# Sets TASK_ID. Called directly (never in a subshell) so `exit 2` propagates.
resolve_task_id() {
    local raw="${1:-}"
    local id="${raw#t}"
    if [[ ! "$id" =~ ^[0-9]+(_[0-9]+)?$ ]]; then
        printf "Error: invalid task id: '%s' (expected N, tN, N_M, or tN_M)\n" \
            "$raw" >&2
        exit 2
    fi
    TASK_ID="$id"
}

# Refuse a root with a `..` segment before ANY filesystem access. Called directly
# (never in a subshell) by every verb, so the exit 2 propagates and nothing has
# been created, modified or deleted when it fires.
validate_root() {
    case "/$SCRATCHPAD_DIR/" in
        */../*) err_usage "scratchpad root '$SCRATCHPAD_DIR' contains a '..' segment" ;;
    esac
}

# Derive the store/lock paths for the resolved TASK_ID. Both derive from the
# root, so an AITASK_SCRATCHPAD_DIR override moves them together.
store_paths_for() {
    STORE_DIR="$SCRATCHPAD_DIR/$TASK_ID"
    STORE_FILE="$STORE_DIR/notes.md"
    HOLDER_FILE="$STORE_DIR/.holder.lock"
    LOCKS_DIR="$SCRATCHPAD_DIR/.locks"
    LOCK_DIR="$LOCKS_DIR/$TASK_ID.lockd"
}

# Print the canonical absolute form of <dir> without creating anything:
# make it absolute, drop empty and `.` segments, canonicalize the deepest
# EXISTING ancestor physically (`cd -P`, portable — no `realpath -m`) and append
# the not-yet-created remainder. Because mkdir only ever creates real
# directories below that ancestor, the result is the same before and after the
# remainder exists. Returns 2 on a `..` segment (validate_root normally refused
# it already) and 4 when the ancestor cannot be entered.
_canonical_key() {
    local abs rest seg prefix="" canon out i=0
    local -a segs=()
    case "$1" in
        /*) abs="$1" ;;
        *)  abs="$PWD/$1" ;;
    esac
    rest="$abs"
    while [[ -n "$rest" ]]; do
        seg="${rest%%/*}"
        if [[ "$rest" == */* ]]; then rest="${rest#*/}"; else rest=""; fi
        case "$seg" in
            ''|.) ;;
            ..)   return 2 ;;
            *)    segs+=("$seg") ;;
        esac
    done
    while (( i < ${#segs[@]} )) && [[ -d "$prefix/${segs[i]}" ]]; do
        prefix="$prefix/${segs[i]}"
        i=$(( i + 1 ))
    done
    canon="$(cd "${prefix:-/}" && pwd -P)" || return 4
    [[ "$canon" == "/" ]] && canon=""
    out="$canon"
    while (( i < ${#segs[@]} )); do
        out="$out/${segs[i]}"
        i=$(( i + 1 ))
    done
    printf '%s\n' "${out:-/}"
}

# Set STORE_KEY or exit 4. The explicit branch matters: a failing substitution
# used directly as an argument (`echo "X:$(f)"`) does not trip errexit and would
# print a success-shaped line with an empty key.
capture_key() {
    if ! STORE_KEY="$(_canonical_key "$STORE_DIR")" || [[ "$STORE_KEY" != /* ]]; then
        printf "Error: cannot canonicalize scratchpad store path '%s'\n" "$STORE_DIR" >&2
        exit 4
    fi
}

# Acquire the lifecycle lock or report LOCK_BUSY and exit 3. NEVER proceed
# unlocked. Only the `.locks` parent is created — never the store itself.
lock_or_busy() {
    # registry_lock_acquire uses a plain `mkdir`, so the parent must exist, and a
    # failure to create it is a WRITE error, not contention — reporting it as
    # LOCK_BUSY after spinning out the timeout would blame a writer that does
    # not exist.
    if ! mkdir -p "$LOCKS_DIR" 2>/dev/null; then
        printf "Error: cannot create lock directory '%s'\n" "$LOCKS_DIR" >&2
        exit 4
    fi
    if [[ ! -w "$LOCKS_DIR" ]]; then
        printf "Error: lock directory '%s' is not writable\n" "$LOCKS_DIR" >&2
        exit 4
    fi
    # The lock path must be a REAL directory or absent: acquire serializes by
    # racing `mkdir "$LOCK_DIR"`, so anything else there would make it spin out
    # its whole timeout. A symlink is rejected even when it points at a
    # directory (`-d` follows it, `mkdir` still fails on the link).
    if [[ -L "$LOCK_DIR" ]]; then
        printf "Error: lock path '%s' is a symlink; expected a real directory\n" \
            "$LOCK_DIR" >&2
        exit 4
    fi
    if [[ -e "$LOCK_DIR" && ! -d "$LOCK_DIR" ]]; then
        printf "Error: lock path '%s' exists but is not a directory\n" "$LOCK_DIR" >&2
        exit 4
    fi
    if ! registry_lock_acquire "$LOCK_DIR" "$LOCK_TIMEOUT"; then
        echo "LOCK_BUSY"
        exit 3
    fi
}

# True while the task file is active: `<TASK_DIR>/t<N>_*.md` for a parent,
# `<TASK_DIR>/t<P>/t<P>_<C>_*.md` for a child. Archived files never match.
task_is_active() {
    local tdir="${TASK_DIR:-aitasks}" f
    if [[ "$TASK_ID" == *_* ]]; then
        local p="${TASK_ID%%_*}" c="${TASK_ID#*_}"
        for f in "$tdir/t$p/t${p}_${c}_"*.md; do
            [[ -e "$f" ]] && return 0
        done
    else
        for f in "$tdir/t${TASK_ID}_"*.md; do
            [[ -e "$f" ]] && return 0
        done
    fi
    return 1
}

# Test-only pause point — see TEST SEAM in the header.
_pause_seam() {
    [[ -n "${AITASK_SCRATCHPAD_PAUSE_FIFO:-}" ]] || return 0
    printf '%s\n' "$1" > "${AITASK_SCRATCHPAD_PAUSE_FIFO}.reached"
    local _line
    read -r _line < "$AITASK_SCRATCHPAD_PAUSE_FIFO" || true
}

# --- open -------------------------------------------------------------------

cmd_open() {
    resolve_task_id "${1:-}"
    shift || true
    [ $# -eq 0 ] || usage
    validate_root
    store_paths_for
    # Before anything is created: a canonicalization failure leaves nothing behind.
    capture_key

    lock_or_busy
    if ! task_is_active; then
        registry_lock_release "$LOCK_DIR"
        echo "NO_TASK"
        return 0
    fi
    _pause_seam open:after_task_check
    if ! mkdir -p "$STORE_DIR" 2>/dev/null; then
        printf "Error: cannot create store directory '%s'\n" "$STORE_DIR" >&2
        exit 4
    fi
    if ! { : >> "$HOLDER_FILE"; } 2>/dev/null; then
        printf "Error: cannot create holder file '%s'\n" "$HOLDER_FILE" >&2
        exit 4
    fi
    registry_lock_release "$LOCK_DIR"
    echo "OPENED:$STORE_KEY/notes.md"
}

# --- save -------------------------------------------------------------------

_save_body() {
    printf '%s' "$SAVE_BUF"
}

cmd_save() {
    resolve_task_id "${1:-}"
    shift || true
    [ $# -eq 0 ] || usage
    validate_root
    store_paths_for

    # Read stdin BEFORE taking the lock; the sentinel keeps trailing newlines.
    # `&&`, not `;`: the substitution's status must be cat's, or a failed or
    # partial read would commit an empty or truncated buffer as a success.
    local buf
    if ! buf="$(cat && printf x)"; then
        echo "Error: could not read the notes text from stdin" >&2
        exit 4
    fi
    buf="${buf%x}"

    lock_or_busy
    if ! task_is_active; then
        registry_lock_release "$LOCK_DIR"
        echo "ARCHIVED"
        return 0
    fi
    if [[ ! -d "$STORE_DIR" ]]; then
        registry_lock_release "$LOCK_DIR"
        echo "ABSENT"
        return 0
    fi
    _pause_seam save:after_exists_check

    # ait_atomic_render refuses a zero-byte result, so an empty buffer removes
    # the file instead.
    if [[ -z "$buf" ]]; then
        if ! rm -f "$STORE_FILE"; then
            printf "Error: could not remove '%s'\n" "$STORE_FILE" >&2
            exit 4
        fi
        registry_lock_release "$LOCK_DIR"
        echo "SAVED:empty"
        return 0
    fi

    SAVE_BUF="$buf"
    if ! ait_atomic_render "$STORE_FILE" _save_body; then
        printf "Error: could not write '%s'\n" "$STORE_FILE" >&2
        exit 4
    fi
    registry_lock_release "$LOCK_DIR"
    local bytes
    bytes="$(printf '%s' "$buf" | wc -c | tr -d '[:space:]')"
    echo "SAVED:$bytes"
}

# --- path -------------------------------------------------------------------

cmd_path() {
    resolve_task_id "${1:-}"
    shift || true
    [ $# -eq 0 ] || usage
    validate_root
    store_paths_for
    capture_key
    echo "$STORE_KEY"
}

# --- prune ------------------------------------------------------------------

cmd_prune() {
    resolve_task_id "${1:-}"
    shift || true
    [ $# -eq 0 ] || usage
    validate_root
    store_paths_for

    # The only pre-lock exit — see LIFECYCLE LOCK in the header.
    if [[ ! -d "$SCRATCHPAD_DIR" ]]; then
        echo "PRUNED:absent"
        return 0
    fi

    lock_or_busy

    # Everything below runs under the lock: an absence check taken before it
    # would miss a first `open` paused between its task check and its mkdir.
    if [[ -L "$STORE_DIR" ]]; then
        printf "Error: refusing to prune '%s' — it is a symlink\n" "$STORE_DIR" >&2
        exit 4
    fi
    if [[ ! -d "$STORE_DIR" ]]; then
        registry_lock_release "$LOCK_DIR"
        echo "PRUNED:absent"
        return 0
    fi

    # Only ever delete under our own root.
    local base canonical
    if ! base="$(cd "$SCRATCHPAD_DIR" && pwd -P)" \
            || ! canonical="$(cd "$STORE_DIR" && pwd -P)"; then
        printf "Error: cannot resolve '%s' for the own-root check\n" "$STORE_DIR" >&2
        exit 4
    fi
    if [[ "$canonical" != "$base/$TASK_ID" ]]; then
        printf "Error: refusing to prune '%s' — it resolves to '%s', outside '%s'\n" \
            "$STORE_DIR" "$canonical" "$base" >&2
        exit 4
    fi

    # Regular files only (notes.md, .holder.lock, a crashed writer's staging
    # temp), then a plain rmdir — never `rm -rf`. Anything else left in the dir
    # is not ours to delete, so the rmdir fails and that is reported.
    find "$STORE_DIR" -maxdepth 1 -type f -exec rm -f {} + 2>/dev/null || true
    if ! rmdir "$STORE_DIR" 2>/dev/null; then
        printf "Error: '%s' still holds entries that are not regular files; left in place\n" \
            "$STORE_DIR" >&2
        exit 4
    fi
    registry_lock_release "$LOCK_DIR"
    echo "PRUNED:$TASK_ID"
}

main() {
    local verb="${1:-}"
    [ -n "$verb" ] || usage
    shift
    case "$verb" in
        open)      cmd_open "$@" ;;
        save)      cmd_save "$@" ;;
        path)      cmd_path "$@" ;;
        prune)     cmd_prune "$@" ;;
        -h|--help) usage ;;
        *)         usage ;;
    esac
}

main "$@"
