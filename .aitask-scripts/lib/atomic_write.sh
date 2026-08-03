#!/usr/bin/env bash
# atomic_write.sh - temp-file + rename file replacement for shell writers (t1379).
#
# Shell sibling of lib/atomic_write.py (t1371); same contract, same guarantees:
#
#   SCOPE -- reader-visible atomicity, NOT writer serialization. The rename
#   guarantees a reader sees either the whole old file or the whole new one. It
#   does NOT serialize a read-modify-write cycle: two concurrent mutations can
#   each render from the same old text, and the second rename silently discards
#   the first. Atomicity makes that loss clean rather than corrupt -- it does
#   not prevent it. A caller that read-modify-writes a shared file must hold its
#   own mutex.
#
#   Atomic *visibility*, not crash durability: there is no fsync, matching
#   atomic_write.py. A crash between the write and the rename leaves the
#   ORIGINAL file intact, which is the property that matters for git-tracked
#   task data.
#
# A plain `> "$file"` truncates the target BEFORE any bytes are written, so a
# concurrent reader can observe the file empty or half-written -- the window
# `ait board`'s live task-frontmatter scan fell into (t1365). A `mv` from
# "${TMPDIR:-/tmp}" is no better: when TMPDIR is on another filesystem the
# rename degrades into a copy, which has the same window.
#
# ---------------------------------------------------------------------------
# RENDERERS MUST NOT RELY ON `set -e`.
#
# ait_atomic_render tests its renderer's exit status, and its callers test its
# own -- so bash disables errexit for everything inside. A renderer shaped like
#
#     echo line1; some_failing_command; printf rest
#
# therefore runs to completion and returns the status of its LAST command,
# committing a partial file. No construct inside this library can restore
# errexit: `if ! fn`, `( set -e; fn )`, `( set -e; trap 'exit 1' ERR; fn )` and
# `( trap 'exit 1' ERR; fn )` were all measured and all committed the partial
# output. So every renderer must guard each fallible command explicitly:
#
#     _my_body() { build_header || return 1; cat "$src" || return 1; }
#
# A pure `echo`/`printf` sequence needs no guards: the only way such a command
# fails is a broken output fd, which fails the trailing write too. Anything
# that can fail on its own -- awk, a loop whose success is decided by a flag
# checked afterwards, a helper function -- needs `|| return 1`.
#
# ait_atomic_render additionally refuses to commit a zero-byte result (override
# with AIT_ATOMIC_ALLOW_EMPTY=1). That is a backstop for a renderer whose output
# fd broke immediately; it does NOT catch a partial file -- the guards above do.
# ---------------------------------------------------------------------------
#
# No EXIT trap, deliberately: bash has a single EXIT trap and lib/archive_utils.sh
# already claims it globally at source time (reached by everything that sources
# task_utils.sh), while aitask_create.sh and aitask_projects.sh install their
# own. A trap here would silently unregister someone else's cleanup. Cleanup is
# inline instead, matching lib/artifact_cache.sh.

if [[ -z "${_AIT_ATOMIC_WRITE_LOADED:-}" ]]; then
_AIT_ATOMIC_WRITE_LOADED=1

# --- ait_atomic_resolve <path> ---------------------------------------------
# Print the fully resolved path: `pwd -P` on the directory (which collapses the
# aitasks/ -> .aitask-data/aitasks/ directory symlink), then follow a FILE
# symlink chain by hand. `readlink -f` is GNU-only -- macOS did not ship it
# until 12.3 -- so the chain is walked explicitly, bounded at 40 hops.
#
# This matters twice over: `> "$dest"` follows a file symlink whereas `mv`
# REPLACES the link, orphaning the backing file; and staging "beside the
# destination" is only same-filesystem if the destination is the resolved one.
ait_atomic_resolve() {
    local p="$1" d b t hops=0
    d="$(cd "$(dirname "$p")" 2>/dev/null && pwd -P)" || { printf '%s\n' "$p"; return 0; }
    b="$(basename "$p")"
    while [[ -L "$d/$b" ]]; do
        hops=$((hops + 1))
        if (( hops > 40 )); then
            echo "atomic_write: too many symlink levels: $p" >&2
            return 1
        fi
        t="$(readlink "$d/$b")" || return 1
        case "$t" in
            /*) d="$(cd "$(dirname "$t")" 2>/dev/null && pwd -P)" || return 1 ;;
            *)  d="$(cd "$d/$(dirname "$t")" 2>/dev/null && pwd -P)" || return 1 ;;
        esac
        b="$(basename "$t")"
    done
    printf '%s\n' "$d/$b"
}

# --- ait_file_mode <path> ---------------------------------------------------
# Octal mode of an existing file; empty when it does not exist. `stat -c` is
# GNU, `stat -f` is BSD -- the fallback chain is the repo idiom (aitask_gate.sh,
# aitask_create.sh). On GNU, `stat -f` means something else entirely, but it is
# only reached when the file is absent, where it fails too.
ait_file_mode() {
    stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null || true
}

# --- ait_atomic_discard <tmp> ----------------------------------------------
# Best-effort removal of a staged temp. Never fails.
ait_atomic_discard() {
    rm -f "${1:-}" 2>/dev/null || true
}

# --- ait_atomic_tmp <resolved_dest> ----------------------------------------
# Create a staging temp beside <resolved_dest> and print its path.
#
# <resolved_dest> MUST already be resolved -- like atomic_write.py's `prepare`,
# this does not follow symlinks itself. Resolving here as well as in the entry
# point would open a TOCTOU window in which a retargeted symlink stages beside
# one backing file and renames onto another.
#
# The temp is dot-prefixed so task-file globs and archive scans never see it,
# and lives in the destination's own directory so the later rename cannot cross
# a filesystem boundary. mkstemp-style temps are created 0600, so the mode is
# set explicitly: the destination's current mode, or -- when it does not exist
# yet -- `0666 & ~umask`, which is what the plain redirection this replaces
# would have produced. Without that, every newly created task file would land
# 0600 instead of 0644.
ait_atomic_tmp() {
    local dest="$1" dir mode tmp
    if [[ -d "$dest" ]]; then
        echo "atomic_write: destination is a directory: $dest" >&2
        return 1
    fi
    dir="$(dirname "$dest")"
    mkdir -p "$dir" || return 1
    tmp="$(mktemp "$dir/.$(basename "$dest").XXXXXX")" || return 1
    mode="$(ait_file_mode "$dest")"
    [[ -n "$mode" ]] || mode="$(printf '%o' $(( 0666 & ~0$(umask) )))"
    chmod "$mode" "$tmp" || { ait_atomic_discard "$tmp"; return 1; }
    printf '%s\n' "$tmp"
}

# --- ait_atomic_commit <tmp> <resolved_dest> -------------------------------
# Move a staged temp into place. Removes the temp on any failure.
#
# The directory check is not paranoia: `mv -f tmp somedir` SUCCEEDS by moving
# the temp inside the directory, so without it a commit onto a directory would
# report success while writing nothing -- whereas the `> "$dest"` it replaces
# fails with "Is a directory".
ait_atomic_commit() {
    local tmp="$1" dest="$2"
    if [[ -d "$dest" ]]; then
        ait_atomic_discard "$tmp"
        echo "atomic_write: destination is a directory: $dest" >&2
        return 1
    fi
    mv -f "$tmp" "$dest" || { ait_atomic_discard "$tmp"; return 1; }
}

# --- ait_atomic_render <dest> <fn> [args...] -------------------------------
# Atomically replace <dest> with whatever `fn [args...]` writes to stdout.
# This is THE pattern every converted write block uses -- do not hand-roll
# `tmp=$(ait_atomic_tmp …); { … } > "$tmp"; ait_atomic_commit …`, because that
# shape leaks the temp when the render fails under `set -e`.
#
# Read the RENDERERS MUST NOT RELY ON `set -e` note at the top of this file
# before writing a renderer.
ait_atomic_render() {
    local dest tmp
    dest="$(ait_atomic_resolve "$1")" || return 1   # resolve exactly once
    shift
    tmp="$(ait_atomic_tmp "$dest")" || return 1
    if ! "$@" > "$tmp"; then
        ait_atomic_discard "$tmp"
        return 1
    fi
    if [[ ! -s "$tmp" && -z "${AIT_ATOMIC_ALLOW_EMPTY:-}" ]]; then
        ait_atomic_discard "$tmp"
        echo "atomic_write: renderer produced an empty file for $dest" >&2
        return 1
    fi
    ait_atomic_commit "$tmp" "$dest"
}

# --- ait_atomic_write_text <dest> <content> --------------------------------
# One-shot replacement for callers that already hold the whole text. Writes
# exactly one trailing newline (command substitution strips any the caller had).
ait_atomic_write_text() {
    local dest tmp
    dest="$(ait_atomic_resolve "$1")" || return 1
    tmp="$(ait_atomic_tmp "$dest")" || return 1
    printf '%s\n' "$2" > "$tmp" || { ait_atomic_discard "$tmp"; return 1; }
    ait_atomic_commit "$tmp" "$dest"
}

fi
